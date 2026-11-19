from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.database import get_db, get_session_factory
from app.core.deps import get_current_user
from app.core.problem_access import get_problem_or_404
from app.models import Role, Submission, User
from app.schemas import RunIn, SubmissionBrief, SubmissionOut, SubmitIn
from app.services.grading import INTERNAL_ERROR
from app.services.judge import Judge, get_judge
from app.services.submissions import process_submission

router = APIRouter(tags=["submissions"])


def judge_dependency() -> Judge:
    try:
        return get_judge()
    except RuntimeError as err:
        raise HTTPException(status_code=503, detail=str(err))


def _aware(moment: datetime) -> datetime:
    # SQLite gives back dates without a time zone; our dates are always UTC.
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


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
    wait = seconds - (datetime.now(timezone.utc) - _aware(last)).total_seconds()
    if wait > 0:
        raise HTTPException(
            status_code=429,
            detail=f"Please wait {int(wait) + 1} more second(s) before trying again.",
            headers={"Retry-After": str(int(wait) + 1)},
        )


def _create(db: Session, user: User, kind: str, **fields) -> Submission:
    sub = Submission(user_id=user.id, kind=kind, status="queued", **fields)
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
    if data.problem_id is not None:
        get_problem_or_404(user, data.problem_id, db)  # only to make sure the person may see it
    _check_cooldown(db, user, "run", get_settings().run_cooldown_seconds)
    sub = _create(
        db, user, "run",
        problem_id=data.problem_id, language=data.language, source_code=data.source_code, stdin=data.stdin,
    )
    background.add_task(process_submission, sub.id, session_factory, judge)
    return sub


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
    problem = get_problem_or_404(user, data.problem_id, db)
    _check_cooldown(db, user, "submit", get_settings().submit_cooldown_seconds)
    sub = _create(db, user, "submit", problem_id=problem.id, language=data.language, source_code=data.source_code)
    background.add_task(process_submission, sub.id, session_factory, judge)
    return sub


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
        if datetime.now(timezone.utc) - _aware(sub.created_at) > patience:
            sub.status = "error"
            sub.verdict = INTERNAL_ERROR
            sub.message = "Judging was interrupted. Please try again."
            sub.finished_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(sub)
    return sub


@router.get("/problems/{problem_id}/submissions", response_model=list[SubmissionBrief])
def my_submissions(problem_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """My own earlier submits for this problem, newest first."""
    get_problem_or_404(user, problem_id, db)
    return db.scalars(
        select(Submission)
        .where(Submission.user_id == user.id, Submission.problem_id == problem_id, Submission.kind == "submit")
        .order_by(Submission.created_at.desc(), Submission.id.desc())
        .limit(20)
    ).all()
