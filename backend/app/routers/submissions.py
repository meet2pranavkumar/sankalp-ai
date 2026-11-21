from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core import clock
from app.core.config import get_settings
from app.core.database import get_db, get_session_factory
from app.core.deps import get_current_user
from app.core.problem_access import get_problem_or_404
from app.models import Assessment, Problem, Role, Submission, User
from app.schemas import RunIn, SubmissionBrief, SubmissionOut, SubmitIn
from app.services.assessments import EXAM, check_submission_allowed
from app.services.grading import INTERNAL_ERROR
from app.services.judge import Judge, get_judge
from app.services.submissions import process_submission

router = APIRouter(tags=["submissions"])


def judge_dependency() -> Judge:
    try:
        return get_judge()
    except RuntimeError as err:
        raise HTTPException(status_code=503, detail=str(err))


def _check_source(source_code: str) -> None:
    limit = get_settings().max_source_bytes
    if len(source_code.encode("utf-8")) > limit:
        raise HTTPException(status_code=422, detail=f"Your code is too long (maximum {limit // 1024} KB).")


def _check_cooldown(db: Session, user: User, kind: str, seconds: float) -> None:
    if seconds <= 0:
        return
    last = db.scalar(
        select(Submission.created_at)
        .where(Submission.user_id == user.id, Submission.kind == kind)
        .order_by(Submission.created_at.desc())
        .limit(1)
    )
    if last is None:
        return
    wait = seconds - (clock.utc_now() - clock.aware(last)).total_seconds()
    if wait > 0:
        raise HTTPException(
            status_code=429,
            detail=f"Please wait {int(wait) + 1} more second(s) before trying again.",
            headers={"Retry-After": str(int(wait) + 1)},
        )


def _create(db: Session, user: User, kind: str, **fields) -> Submission:
    sub = Submission(user_id=user.id, kind=kind, status="queued", created_at=clock.utc_now(), **fields)
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


@router.post("/run", response_model=SubmissionOut, status_code=202)
def run_code(
    data: RunIn,
    background: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    judge: Judge = Depends(judge_dependency),
    session_factory: sessionmaker = Depends(get_session_factory),
):
    """Try the code with your own input. Poll GET /submissions/{id} for the answer."""
    _check_source(data.source_code)
    if data.assessment_id is not None:
        check_submission_allowed(db, user, data.assessment_id, data.problem_id, clock.utc_now())
    elif data.problem_id is not None:
        get_problem_or_404(user, data.problem_id, db)  # only to make sure the person may see it
    _check_cooldown(db, user, "run", get_settings().run_cooldown_seconds)
    sub = _create(
        db, user, "run", assessment_id=data.assessment_id,
        problem_id=data.problem_id, language=data.language, source_code=data.source_code, stdin=data.stdin,
    )
    background.add_task(process_submission, sub.id, session_factory, judge)
    return present_submission(sub, user, db)


@router.post("/submissions", response_model=SubmissionOut, status_code=202)
def submit_code(
    data: SubmitIn,
    background: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    judge: Judge = Depends(judge_dependency),
    session_factory: sessionmaker = Depends(get_session_factory),
):
    """Judge the code against all test cases. Poll GET /submissions/{id} for the verdict."""
    _check_source(data.source_code)
    if data.assessment_id is not None:
        check_submission_allowed(db, user, data.assessment_id, data.problem_id, clock.utc_now())
        problem = db.get(Problem, data.problem_id)
    else:
        problem = get_problem_or_404(user, data.problem_id, db)
    _check_cooldown(db, user, "submit", get_settings().submit_cooldown_seconds)
    sub = _create(
        db, user, "submit", assessment_id=data.assessment_id, problem_id=problem.id,
        language=data.language, source_code=data.source_code,
    )
    background.add_task(process_submission, sub.id, session_factory, judge)
    return present_submission(sub, user, db)


def exam_results_hidden(sub: Submission, viewer: User, db: Session, cache: dict | None = None) -> bool:
    """A student must not see the verdict of an exam answer until the teacher publishes the results.
    (Run results are different: they are the student's own test and are always shown.)"""
    if sub.assessment_id is None or sub.kind != "submit" or viewer.id != sub.user_id or viewer.role != Role.student.value:
        return False
    if cache is not None and sub.assessment_id in cache:
        return cache[sub.assessment_id]
    a = db.get(Assessment, sub.assessment_id)
    hidden = a is not None and a.type == EXAM and not a.results_published
    if cache is not None:
        cache[sub.assessment_id] = hidden
    return hidden


HIDDEN_FIELDS = dict(
    verdict=None, passed_count=None, total_count=None, runtime_ms=None, memory_kb=None,
    stdout=None, stderr=None, compile_output=None, message=None, results=None,
)


def present_submission(sub: Submission, viewer: User, db: Session) -> SubmissionOut:
    out = SubmissionOut.model_validate(sub)
    if exam_results_hidden(sub, viewer, db):
        out = out.model_copy(update={**HIDDEN_FIELDS, "hidden": True})
    return out


def _can_read(user: User, sub: Submission, db: Session) -> bool:
    if sub.user_id == user.id or user.role == Role.super_admin.value:
        return True
    if user.role in (Role.teacher.value, Role.admin.value):
        owner = db.get(User, sub.user_id)
        return owner is not None and owner.college_id == user.college_id
    return False


@router.get("/submissions/{submission_id}", response_model=SubmissionOut)
def get_submission(submission_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sub = db.get(Submission, submission_id)
    if sub is None or not _can_read(user, sub, db):
        raise HTTPException(status_code=404, detail="Submission not found.")
    # If the server restarted while judging, the job is lost. Do not leave the student waiting forever.
    if sub.status in ("queued", "running"):
        patience = timedelta(seconds=get_settings().judge_timeout_seconds + 30)
        if clock.utc_now() - clock.aware(sub.created_at) > patience:
            sub.status = "error"
            sub.verdict = INTERNAL_ERROR
            sub.message = "Judging was interrupted. Please try again."
            sub.finished_at = clock.utc_now()
            db.commit()
            db.refresh(sub)
    return present_submission(sub, user, db)


@router.get("/problems/{problem_id}/submissions", response_model=list[SubmissionBrief])
def my_submissions(problem_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """My own earlier submits for this problem, newest first."""
    get_problem_or_404(user, problem_id, db)
    subs = db.scalars(
        select(Submission)
        .where(Submission.user_id == user.id, Submission.problem_id == problem_id, Submission.kind == "submit")
        .order_by(Submission.created_at.desc(), Submission.id.desc())
        .limit(20)
    ).all()
    cache: dict = {}
    briefs = []
    for sub in subs:
        brief = SubmissionBrief.model_validate(sub)
        if exam_results_hidden(sub, user, db, cache):
            brief = brief.model_copy(update=dict(verdict=None, passed_count=None, total_count=None, runtime_ms=None, hidden=True))
        briefs.append(brief)
    return briefs
