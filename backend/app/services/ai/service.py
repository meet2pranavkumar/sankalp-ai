"""The rules of the AI helper: who may ask, how often, and what a student is allowed to see."""
from dataclasses import dataclass
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.clock import aware
from app.core.config import get_settings
from app.models import AIRequest, Assessment, AssessmentProblem, BatchMember, Problem, User
from app.schemas import AIRecentOut, AIUsageOut
from app.services.ai.base import AIProvider, ProviderError
from app.services.ai.guard import violations
from app.services.ai.prompts import build_explain_prompt, build_hint_prompt
from app.services.assessments import user_has_active_exam

WINDOW = timedelta(hours=24)

# Shown instead of an AI answer that looked like a solution. They help without giving anything away.
FALLBACK = {
    ("hint", 1): "Let's think about it together. Read the problem again. What is the input, and what must the output be? "
                 "Try the first sample by hand and write down every step you take.",
    ("hint", 2): "Break the problem into small steps. Write the steps in your own words first. "
                 "Then turn each step into code, one step at a time, and run it after every step.",
    ("hint", 3): "Write the steps in plain words, one step per line. Then look at each line and ask: "
                 "can I write this as one or two lines of code?",
    ("explain", None): "Read the error message slowly. It shows a line number. Look at that line and at the line before it. "
                       "Check for a missing semicolon or bracket, a spelling mistake, or a variable that was never created.",
}


# ---------------------------------------------------------------- may the student use the helper right now?
def block_reason(db: Session, user: User, problem_id: int, now: datetime) -> str | None:
    """Why the helper must stay closed for this student and problem, or None if it may open."""
    if user_has_active_exam(db, user, now):
        return "The AI helper is switched off during an exam."
    mine = select(BatchMember.batch_id).where(BatchMember.user_id == user.id)
    assignments = db.scalars(
        select(Assessment)
        .join(AssessmentProblem, AssessmentProblem.assessment_id == Assessment.id)
        .where(
            AssessmentProblem.problem_id == problem_id,
            Assessment.type == "assignment",
            Assessment.ai_hints_allowed.is_(False),
            Assessment.is_published.is_(True),
            Assessment.batch_id.in_(mine),
        )
    ).all()
    if any(aware(a.starts_at) <= now < aware(a.ends_at) for a in assignments):
        return "Your teacher turned the AI helper off for this assignment."
    return None


# ---------------------------------------------------------------- how much has this student used?
@dataclass
class Usage:
    hints_used: int
    explains_used: int
    user_total: int
    max_level: int
    last_hint_at: datetime | None
    recent: list[AIRequest]


def usage_for(db: Session, user: User, problem_id: int, now: datetime) -> Usage:
    """Counts the last 24 hours. Requests that failed because the AI service was down do not count."""
    since = now - WINDOW
    rows = [
        r for r in db.scalars(select(AIRequest).where(AIRequest.user_id == user.id).order_by(desc(AIRequest.created_at)).limit(500))
        if aware(r.created_at) >= since and r.status != "error"
    ]
    mine = [r for r in rows if r.problem_id == problem_id]
    hints = [r for r in mine if r.kind == "hint"]
    return Usage(
        hints_used=len(hints),
        explains_used=sum(1 for r in mine if r.kind == "explain"),
        user_total=len(rows),
        max_level=max((r.level or 0 for r in hints), default=0),
        last_hint_at=max((aware(r.created_at) for r in hints), default=None),
        recent=mine[:10],
    )


def retry_after(u: Usage, now: datetime) -> int:
    if u.last_hint_at is None:
        return 0
    wait = get_settings().ai_hint_cooldown_seconds - (now - u.last_hint_at).total_seconds()
    return max(0, int(wait) + (1 if wait > 0 else 0))


def build_usage(db: Session, user: User, problem_id: int, now: datetime, enabled: bool, reason: str | None) -> AIUsageOut:
    settings = get_settings()
    u = usage_for(db, user, problem_id, now)
    levels = [1, 2, 3][: min(u.max_level + 1, 3)] if u.hints_used < settings.ai_hints_per_problem_per_day else []
    return AIUsageOut(
        enabled=enabled, blocked_reason=reason,
        hints_used=u.hints_used, hints_limit=settings.ai_hints_per_problem_per_day,
        explains_used=u.explains_used, explains_limit=settings.ai_explains_per_problem_per_day,
        available_levels=levels if enabled else [], retry_after_seconds=retry_after(u, now),
        recent=[AIRecentOut(id=r.id, kind=r.kind, level=r.level, text=r.response_text, created_at=r.created_at) for r in u.recent],
    )


# ---------------------------------------------------------------- asking
def _too_many(message: str, wait: int | None = None) -> HTTPException:
    headers = {"Retry-After": str(wait)} if wait else None
    return HTTPException(status_code=429, detail=message, headers=headers)


def ask(
    db: Session, user: User, provider: AIProvider, problem: Problem, kind: str, level: int | None,
    language: str, code: str, error_text: str, now: datetime,
) -> AIRequest:
    settings = get_settings()
    u = usage_for(db, user, problem.id, now)

    if u.user_total >= settings.ai_user_daily_cap:
        raise _too_many("You have asked the AI helper a lot today. Please try again tomorrow, or ask your teacher.")
    if kind == "hint":
        if u.hints_used >= settings.ai_hints_per_problem_per_day:
            raise _too_many(
                f"You have used all {settings.ai_hints_per_problem_per_day} hints for this problem today. "
                "Try again tomorrow, or ask your teacher."
            )
        wait = retry_after(u, now)
        if wait > 0:
            raise _too_many(f"Take a few minutes to try the hint first. You can ask again in {wait} second(s).", wait)
        if level > u.max_level + 1:
            raise HTTPException(status_code=409, detail=f"Read hint {level - 1} first. Hints open one after the other.")
    elif u.explains_used >= settings.ai_explains_per_problem_per_day:
        raise _too_many("You have used all the error explanations for this problem today. Try again tomorrow.")

    samples = [(t.input, t.expected_output) for t in problem.test_cases if not t.is_hidden]  # hidden tests are never sent
    tokens_in = tokens_out = 0
    text, flagged, fell_back = "", False, False
    try:
        for attempt in range(2):
            strict = attempt == 1
            if kind == "hint":
                system, user_msg = build_hint_prompt(problem.title, problem.statement_md, samples, language, code, level, strict)
            else:
                system, user_msg = build_explain_prompt(problem.title, problem.statement_md, language, code, error_text, strict)
            result = provider.complete(system, user_msg, settings.ai_max_output_tokens)
            tokens_in += result.input_tokens or 0
            tokens_out += result.output_tokens or 0
            text = result.text.strip()
            problems = violations(text, kind, level)
            if not problems:
                flagged = attempt == 1  # the first answer was refused, the second was fine
                break
            flagged = True
        else:  # both answers looked like solutions: show a safe text instead
            text, fell_back = FALLBACK[(kind, level if kind == "hint" else None)], True
    except ProviderError as err:
        db.add(AIRequest(user_id=user.id, problem_id=problem.id, kind=kind, level=level, language=language,
                         status="error", response_text=str(err), created_at=now))
        db.commit()
        raise HTTPException(status_code=503, detail=str(err)) from None

    row = AIRequest(
        user_id=user.id, problem_id=problem.id, kind=kind, level=level, language=language,
        status="fallback" if fell_back else "ok", response_text=text, flagged=flagged,
        input_tokens=tokens_in or None, output_tokens=tokens_out or None, created_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
