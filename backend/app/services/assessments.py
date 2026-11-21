"""The rules of assignments and exams. Time is always passed in, so tests can control it."""
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.access import can_access_batch
from app.core.clock import aware
from app.models import (
    Assessment, AssessmentAttempt, AssessmentDraft, AssessmentProblem, Batch, BatchMember, Role, Submission, User,
)

ASSIGNMENT = "assignment"
EXAM = "exam"
STAFF_ROLES = (Role.teacher.value, Role.admin.value)


# ---------------------------------------------------------------- time and status
def personal_deadline(a: Assessment, now: datetime) -> datetime:
    """An exam gives each student duration_min from when they start, but never past the end of the window."""
    return min(now + timedelta(minutes=a.duration_min), aware(a.ends_at))


def attempt_active(attempt: AssessmentAttempt | None, now: datetime) -> bool:
    return attempt is not None and attempt.finished_at is None and now < aware(attempt.deadline_at)


def student_status(a: Assessment, attempt: AssessmentAttempt | None, now: datetime) -> str:
    starts, ends = aware(a.starts_at), aware(a.ends_at)
    if a.type == ASSIGNMENT:
        if now < starts:
            return "upcoming"
        return "open" if now < ends else "closed"
    if attempt is not None:
        return "in_progress" if attempt_active(attempt, now) else "finished"
    if now < starts:
        return "upcoming"
    return "ready" if now < ends else "missed"


def student_sees_problems(a: Assessment, attempt: AssessmentAttempt | None, now: datetime) -> bool:
    if a.type == ASSIGNMENT:
        return now >= aware(a.starts_at)
    return attempt is not None  # exam questions appear only after the student presses Start


def student_may_see_marks(a: Assessment) -> bool:
    """Exam: nothing until the teacher publishes. Assignment: the automatic marks are live."""
    return a.type == ASSIGNMENT or a.results_published


def student_may_see_final(a: Assessment) -> bool:
    return a.results_published  # teacher changes and comments


# ---------------------------------------------------------------- who may see an assessment
def can_manage(user: User, a: Assessment, db: Session) -> bool:
    if user.role not in STAFF_ROLES or a.college_id != user.college_id:
        return False
    batch = db.get(Batch, a.batch_id)
    return batch is not None and can_access_batch(user, batch, db)


def is_batch_member(db: Session, user: User, batch_id: int) -> bool:
    return db.scalar(
        select(BatchMember.id).where(BatchMember.batch_id == batch_id, BatchMember.user_id == user.id)
    ) is not None


def get_assessment_for(user: User, assessment_id: int, db: Session) -> Assessment:
    """Teachers and admins: ones they manage. Students: published ones for their batch. Everyone else: not found."""
    a = db.get(Assessment, assessment_id)
    ok = False
    if a is not None:
        if user.role in STAFF_ROLES:
            ok = can_manage(user, a, db)
        elif user.role == Role.student.value:
            ok = a.is_published and a.college_id == user.college_id and is_batch_member(db, user, a.batch_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Assessment not found.")
    return a


def get_managed_assessment(user: User, assessment_id: int, db: Session) -> Assessment:
    a = get_assessment_for(user, assessment_id, db)
    if not can_manage(user, a, db):
        raise HTTPException(status_code=403, detail="Only your teacher can do this.")
    return a


def get_attempt(db: Session, assessment_id: int, user_id: int) -> AssessmentAttempt | None:
    return db.scalar(
        select(AssessmentAttempt).where(
            AssessmentAttempt.assessment_id == assessment_id, AssessmentAttempt.user_id == user_id
        )
    )


def has_activity(db: Session, a: Assessment) -> bool:
    """Once anyone started or answered, the problems and type cannot change any more."""
    attempt = db.scalar(select(AssessmentAttempt.id).where(AssessmentAttempt.assessment_id == a.id).limit(1))
    sub = db.scalar(select(Submission.id).where(Submission.assessment_id == a.id).limit(1))
    draft = db.scalar(select(AssessmentDraft.id).where(AssessmentDraft.assessment_id == a.id).limit(1))
    return attempt is not None or sub is not None or draft is not None


# ---------------------------------------------------------------- hiding exam problems from other students
def locked_problem_ids(db: Session, now: datetime) -> set[int]:
    """Problems students must not open from the normal Problems page.

    An exam's problems are locked until the exam window ends. An assignment's problems are locked until it starts.
    Students reach them only through the assessment itself."""
    rows = db.execute(
        select(AssessmentProblem.problem_id, Assessment.type, Assessment.starts_at, Assessment.ends_at).join(
            Assessment, Assessment.id == AssessmentProblem.assessment_id
        )
    ).all()
    locked = set()
    for problem_id, kind, starts_at, ends_at in rows:
        if (kind == EXAM and now < aware(ends_at)) or (kind == ASSIGNMENT and now < aware(starts_at)):
            locked.add(problem_id)
    return locked


def user_has_active_exam(db: Session, user: User, now: datetime) -> bool:
    """True while this student is inside an exam. The AI helper (Phase 6) must stay off then."""
    attempts = db.scalars(
        select(AssessmentAttempt).where(AssessmentAttempt.user_id == user.id, AssessmentAttempt.finished_at.is_(None))
    ).all()
    return any(now < aware(at.deadline_at) for at in attempts)


# ---------------------------------------------------------------- may this answer be accepted?
def check_submission_allowed(db: Session, user: User, assessment_id: int, problem_id: int | None, now: datetime) -> Assessment:
    if user.role != Role.student.value:
        raise HTTPException(status_code=403, detail="Only students take assignments and exams.")
    a = get_assessment_for(user, assessment_id, db)
    if problem_id is None or problem_id not in {ap.problem_id for ap in a.problems}:
        raise HTTPException(status_code=404, detail="This problem is not part of the assessment.")
    if a.type == ASSIGNMENT:
        if now < aware(a.starts_at):
            raise HTTPException(status_code=403, detail="This assignment has not started yet.")
        if now >= aware(a.ends_at):
            raise HTTPException(status_code=403, detail="This assignment is closed.")
        return a
    attempt = get_attempt(db, a.id, user.id)
    if attempt is None:
        raise HTTPException(status_code=403, detail="Press Start to begin the exam first.")
    if not attempt_active(attempt, now):
        raise HTTPException(status_code=403, detail="Your time is over. No more answers can be sent.")
    return a


# ---------------------------------------------------------------- marks
@dataclass
class ProblemScore:
    problem_id: int
    marks: float
    possible: float
    passed: int
    total: int
    attempted: bool


@dataclass
class Sheet:
    per_problem: list[ProblemScore] = field(default_factory=list)
    auto_marks: float = 0.0
    pending: int = 0
    judge_errors: int = 0


def compute_sheets(db: Session, a: Assessment, user_ids: list[int]) -> dict[int, Sheet]:
    """Automatic marks, worked out fresh every time from the submissions.

    For each problem the BEST submission counts: marks x (tests passed / tests in total)."""
    best: dict[tuple[int, int], tuple[float, int, int]] = {}
    attempted: set[tuple[int, int]] = set()
    pending: dict[int, int] = {}
    errors: dict[int, int] = {}
    rows = db.execute(
        select(Submission.user_id, Submission.problem_id, Submission.status, Submission.passed_count, Submission.total_count)
        .where(Submission.assessment_id == a.id, Submission.kind == "submit", Submission.user_id.in_(user_ids or [0]))
    ).all()
    for user_id, problem_id, status, passed, total in rows:
        attempted.add((user_id, problem_id))
        if status in ("queued", "running"):
            pending[user_id] = pending.get(user_id, 0) + 1
        elif status == "error":
            errors[user_id] = errors.get(user_id, 0) + 1
        elif status == "done" and total:
            ratio = passed / total
            if (user_id, problem_id) not in best or ratio > best[(user_id, problem_id)][0]:
                best[(user_id, problem_id)] = (ratio, passed, total)

    sheets: dict[int, Sheet] = {}
    for user_id in user_ids:
        sheet = Sheet(pending=pending.get(user_id, 0), judge_errors=errors.get(user_id, 0))
        for ap in a.problems:
            ratio, passed, total = best.get((user_id, ap.problem_id), (0.0, 0, 0))
            sheet.per_problem.append(
                ProblemScore(ap.problem_id, round(ap.marks * ratio, 2), ap.marks, passed, total, (user_id, ap.problem_id) in attempted)
            )
        sheet.auto_marks = round(sum(p.marks for p in sheet.per_problem), 2)
        sheets[user_id] = sheet
    return sheets


def total_marks(a: Assessment) -> float:
    return round(sum(ap.marks for ap in a.problems), 2)


# ---------------------------------------------------------------- finishing an exam
def needs_finalize(a: Assessment, attempt: AssessmentAttempt, now: datetime) -> bool:
    return attempt.finalized_at is None and (
        attempt.finished_at is not None or now >= aware(attempt.deadline_at) or now >= aware(a.ends_at)
    )


def finalize_attempt(db: Session, a: Assessment, attempt: AssessmentAttempt, now: datetime) -> list[Submission]:
    """Submit, for the student, the last code they saved but never submitted. Safe to call twice."""
    if attempt.finalized_at is not None:
        return []
    created: list[Submission] = []
    drafts = db.scalars(
        select(AssessmentDraft).where(AssessmentDraft.assessment_id == a.id, AssessmentDraft.user_id == attempt.user_id)
    ).all()
    for draft in drafts:
        if not draft.source_code.strip():
            continue
        last = db.scalar(
            select(func.max(Submission.created_at)).where(
                Submission.assessment_id == a.id, Submission.user_id == attempt.user_id,
                Submission.problem_id == draft.problem_id, Submission.kind == "submit",
            )
        )
        if last is not None and aware(draft.updated_at) <= aware(last):
            continue  # that code (or newer code) was already submitted
        created.append(
            Submission(
                user_id=attempt.user_id, problem_id=draft.problem_id, assessment_id=a.id, kind="submit",
                language=draft.language, source_code=draft.source_code, status="queued", created_at=now,
            )
        )
    attempt.finalized_at = now
    db.add_all(created)
    db.commit()
    for sub in created:
        db.refresh(sub)
    return created
