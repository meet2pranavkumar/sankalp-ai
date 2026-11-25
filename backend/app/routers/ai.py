from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import clock
from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import require_roles
from app.core.problem_access import get_problem_or_404
from app.models import AIRequest, Batch, BatchMember, Problem, Role, User
from app.schemas import AIAnswerOut, AIInsightRow, AIRequestRow, AIUsageOut, ExplainIn, HintIn
from app.services.ai import get_ai_provider
from app.services.ai.base import AIProvider
from app.services.ai.service import ask, block_reason, build_usage

router = APIRouter(prefix="/ai", tags=["ai"])
students_only = require_roles(Role.student)
staff = require_roles(Role.teacher, Role.admin)

NOT_SET_UP = "The AI helper is not set up yet. Ask your teacher."


def ai_provider_dependency() -> AIProvider | None:
    return get_ai_provider()


def _open_for(db: Session, user: User, problem_id: int, provider, now) -> None:
    """Raises if the helper must stay closed. The exam check comes first, so it holds even for other problems."""
    reason = block_reason(db, user, problem_id, now)
    if reason:
        raise HTTPException(status_code=403, detail=reason)
    if provider is None:
        raise HTTPException(status_code=503, detail=NOT_SET_UP)


def _too_long(code: str) -> None:
    if len(code.encode("utf-8")) > get_settings().max_source_bytes:
        raise HTTPException(status_code=422, detail="Your code is too long.")


def _answer(db: Session, user: User, row: AIRequest, now) -> AIAnswerOut:
    return AIAnswerOut(
        id=row.id, kind=row.kind, level=row.level, text=row.response_text,
        usage=build_usage(db, user, row.problem_id, now, enabled=True, reason=None),
    )


@router.get("/usage", response_model=AIUsageOut)
def usage(
    problem_id: int, user: User = Depends(students_only), db: Session = Depends(get_db),
    provider: AIProvider | None = Depends(ai_provider_dependency),
):
    """What the student has used today, and whether the helper is open. The page calls this to draw its buttons."""
    now = clock.utc_now()
    reason = block_reason(db, user, problem_id, now)
    if reason is None and provider is None:
        reason = NOT_SET_UP
    if reason is None:
        get_problem_or_404(user, problem_id, db)  # a problem the student cannot see gets a 404
    return build_usage(db, user, problem_id, now, enabled=reason is None, reason=reason)


@router.post("/hint", response_model=AIAnswerOut)
def hint(
    data: HintIn, user: User = Depends(students_only), db: Session = Depends(get_db),
    provider: AIProvider | None = Depends(ai_provider_dependency),
):
    now = clock.utc_now()
    _open_for(db, user, data.problem_id, provider, now)
    _too_long(data.source_code)
    problem = get_problem_or_404(user, data.problem_id, db)
    row = ask(db, user, provider, problem, "hint", data.level, data.language, data.source_code, "", now)
    return _answer(db, user, row, now)


@router.post("/explain-error", response_model=AIAnswerOut)
def explain_error(
    data: ExplainIn, user: User = Depends(students_only), db: Session = Depends(get_db),
    provider: AIProvider | None = Depends(ai_provider_dependency),
):
    now = clock.utc_now()
    _open_for(db, user, data.problem_id, provider, now)
    _too_long(data.source_code)
    problem = get_problem_or_404(user, data.problem_id, db)
    row = ask(db, user, provider, problem, "explain", None, data.language, data.source_code, data.error_text, now)
    return _answer(db, user, row, now)


# ---------------------------------------------------------------- what teachers see
def _students_in_scope(db: Session, user: User) -> set[int]:
    """Teachers see the students of their own batches. Admins see every student of the college."""
    if user.role == Role.admin.value:
        return set(db.scalars(select(User.id).where(User.college_id == user.college_id, User.role == Role.student.value)))
    query = (
        select(BatchMember.user_id)
        .join(Batch, Batch.id == BatchMember.batch_id)
        .where(Batch.college_id == user.college_id, Batch.created_by == user.id)
    )
    return set(db.scalars(query))


def _recent_requests(db: Session, scope: set[int], days: int, problem_id: int | None = None) -> list[AIRequest]:
    since = clock.utc_now() - timedelta(days=days)
    query = select(AIRequest).where(AIRequest.user_id.in_(scope or {0})).order_by(AIRequest.created_at.desc()).limit(5000)
    if problem_id is not None:
        query = query.where(AIRequest.problem_id == problem_id)
    return [r for r in db.scalars(query) if clock.aware(r.created_at) >= since]


@router.get("/insights", response_model=list[AIInsightRow])
def insights(
    days: int = Query(default=30, ge=1, le=365), user: User = Depends(staff), db: Session = Depends(get_db)
):
    """Which problems make students ask for help most. A long list here means the topic needs another lesson."""
    rows = _recent_requests(db, _students_in_scope(db, user), days)
    titles = {p.id: p.title for p in db.scalars(select(Problem).where(Problem.id.in_({r.problem_id for r in rows} or {0})))}
    grouped: dict[int, list[AIRequest]] = {}
    for r in rows:
        grouped.setdefault(r.problem_id, []).append(r)
    out = [
        AIInsightRow(
            problem_id=pid, title=titles.get(pid, "?"),
            students=len({r.user_id for r in items}), requests=len(items),
            hints=sum(1 for r in items if r.kind == "hint"), explains=sum(1 for r in items if r.kind == "explain"),
            level3=sum(1 for r in items if r.level == 3), flagged=sum(1 for r in items if r.flagged),
            errors=sum(1 for r in items if r.status == "error"),
            last_at=max(items, key=lambda r: clock.aware(r.created_at)).created_at,
        )
        for pid, items in grouped.items()
    ]
    return sorted(out, key=lambda r: (-r.requests, r.title))


@router.get("/requests", response_model=list[AIRequestRow])
def list_requests(
    problem_id: int, days: int = Query(default=30, ge=1, le=365),
    user: User = Depends(staff), db: Session = Depends(get_db),
):
    """The actual questions and answers for one problem, newest first, so a teacher can see what students were told."""
    rows = _recent_requests(db, _students_in_scope(db, user), days, problem_id)[:200]
    people = {u.id: u for u in db.scalars(select(User).where(User.id.in_({r.user_id for r in rows} or {0})))}
    return [
        AIRequestRow(
            id=r.id, student_name=people[r.user_id].name, student_email=people[r.user_id].email, kind=r.kind,
            level=r.level, status=r.status, flagged=r.flagged, text=r.response_text, created_at=r.created_at,
        )
        for r in rows
    ]
