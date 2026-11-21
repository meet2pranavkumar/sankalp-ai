import csv
import io
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import clock
from app.core.access import can_access_batch
from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.core.problem_access import can_view_problem
from app.models import (
    Assessment, AssessmentAttempt, AssessmentDraft, AssessmentProblem, AssessmentResult, Batch, BatchMember,
    Problem, Role, Submission, User,
)
from app.routers.problems import present_problem
from app.routers.submissions import exam_results_hidden
from app.schemas import (
    AssessmentIn, AssessmentOut, AssessmentPatch, AssessmentProblemOut, AssessmentSummary, AttemptOut, DraftIn,
    DraftOut, MyResultOut, OverrideIn, ProblemOut, ProblemScoreOut, ResultRow, ResultsOut, SubmissionBrief,
)
from app.services.assessments import (
    ASSIGNMENT, EXAM, STAFF_ROLES, ProblemScore, attempt_active, can_manage, compute_sheets, finalize_attempt,
    get_assessment_for, get_attempt, get_managed_assessment, has_activity, needs_finalize, personal_deadline,
    student_may_see_final, student_may_see_marks, student_sees_problems, student_status, total_marks,
)
from app.services.finalizer import Finalizer

router = APIRouter(tags=["assessments"])
staff = require_roles(Role.teacher, Role.admin)
students = require_roles(Role.student)
participants = require_roles(Role.teacher, Role.admin, Role.student)

STUCK_AFTER = timedelta(seconds=30)


# ---------------------------------------------------------------- helpers
def _score_out(p: ProblemScore) -> ProblemScoreOut:
    return ProblemScoreOut(
        problem_id=p.problem_id, marks=p.marks, possible=p.possible, passed=p.passed, total=p.total, attempted=p.attempted
    )


def _overrides(db: Session, a: Assessment) -> dict[int, AssessmentResult]:
    return {r.user_id: r for r in db.scalars(select(AssessmentResult).where(AssessmentResult.assessment_id == a.id))}


def _problem_info(db: Session, a: Assessment) -> dict[int, Problem]:
    ids = [ap.problem_id for ap in a.problems]
    return {p.id: p for p in db.scalars(select(Problem).where(Problem.id.in_(ids or [0])))}


def _student_marks(db: Session, a: Assessment, user: User, sheet=None) -> float | None:
    """The number a student may see for this assessment, or None."""
    if not student_may_see_marks(a):
        return None
    sheet = sheet or compute_sheets(db, a, [user.id])[user.id]
    if student_may_see_final(a):
        override = _overrides(db, a).get(user.id)
        if override is not None and override.override_marks is not None:
            return override.override_marks
    return sheet.auto_marks


def _summary(db: Session, a: Assessment, user: User, now, attempt=None) -> AssessmentSummary:
    batch = db.get(Batch, a.batch_id)
    is_staff = user.role in STAFF_ROLES
    return AssessmentSummary(
        id=a.id, title=a.title, type=a.type, batch_id=a.batch_id, batch_name=batch.name if batch else "",
        starts_at=a.starts_at, ends_at=a.ends_at, duration_min=a.duration_min,
        is_published=a.is_published, results_published=a.results_published,
        total_marks=total_marks(a), problem_count=len(a.problems),
        status=None if is_staff else student_status(a, attempt, now),
        my_marks=None if is_staff else _student_marks(db, a, user),
        can_manage=is_staff and can_manage(user, a, db),
    )


def finalize_all(db: Session, a: Assessment, now, finalizer: Finalizer) -> None:
    """Submit saved drafts for every student whose time is over, and judge them."""
    created = []
    for attempt in db.scalars(select(AssessmentAttempt).where(AssessmentAttempt.assessment_id == a.id)).all():
        if needs_finalize(a, attempt, now):
            created += finalize_attempt(db, a, attempt, now)
    finalizer.schedule(created)


def _detail(db: Session, a: Assessment, user: User, now, finalizer: Finalizer) -> AssessmentOut:
    is_staff = user.role in STAFF_ROLES
    attempt = None if is_staff else get_attempt(db, a.id, user.id)
    if attempt is not None and needs_finalize(a, attempt, now):  # their time ran out: submit what they saved
        finalizer.schedule(finalize_attempt(db, a, attempt, now))

    info = _problem_info(db, a)
    sheet = None
    show_scores = False
    if is_staff:
        visible = True
    else:
        visible = student_sees_problems(a, attempt, now)
        show_scores = visible and student_may_see_marks(a)
        if show_scores:
            sheet = compute_sheets(db, a, [user.id])[user.id]
    scores = {p.problem_id: p for p in sheet.per_problem} if sheet else {}

    problems = None
    if visible:
        problems = [
            AssessmentProblemOut(
                problem_id=ap.problem_id, title=info[ap.problem_id].title, difficulty=info[ap.problem_id].difficulty,
                marks=ap.marks, position=ap.position,
                score=_score_out(scores[ap.problem_id]) if ap.problem_id in scores else None,
            )
            for ap in a.problems
        ]
    base = _summary(db, a, user, now, attempt)
    return AssessmentOut(
        **base.model_dump(), description=a.description, server_now=now,
        attempt=AttemptOut(started_at=attempt.started_at, deadline_at=attempt.deadline_at, finished_at=attempt.finished_at) if attempt else None,
        problems=problems, has_activity=has_activity(db, a),
    )


def _validate_schedule(kind, starts, ends, duration, now, creating: bool) -> None:
    if ends <= starts:
        raise HTTPException(status_code=422, detail="The end time must be after the start time.")
    if creating and ends <= now:
        raise HTTPException(status_code=422, detail="The end time must be in the future.")
    if kind == EXAM:
        if duration is None:
            raise HTTPException(status_code=422, detail="An exam needs a duration in minutes.")
        if duration > (ends - starts).total_seconds() / 60:
            raise HTTPException(status_code=422, detail="The exam duration cannot be longer than the time window.")
    elif duration is not None:
        raise HTTPException(status_code=422, detail="An assignment has no duration. Leave it empty.")


def _make_problem_rows(db: Session, user: User, items) -> list[AssessmentProblem]:
    rows = []
    for position, item in enumerate(items, start=1):
        problem = db.get(Problem, item.problem_id)
        if problem is None or not can_view_problem(user, problem):
            raise HTTPException(status_code=404, detail=f"Problem {item.problem_id} not found.")
        rows.append(AssessmentProblem(problem_id=item.problem_id, marks=item.marks, position=position))
    return rows


def _batch_students(db: Session, a: Assessment) -> list[User]:
    return db.scalars(
        select(User)
        .join(BatchMember, BatchMember.user_id == User.id)
        .where(BatchMember.batch_id == a.batch_id, User.role == Role.student.value)
        .order_by(func.lower(User.name), User.id)
    ).unique().all()


def _result_status(a: Assessment, attempt, sheet, now) -> str:
    if a.type == EXAM:
        if attempt is None:
            return "not_started"
        return "in_progress" if attempt_active(attempt, now) else "finished"
    return "submitted" if any(p.attempted for p in sheet.per_problem) else "no_submission"


def _build_rows(db: Session, a: Assessment, members: list[User], now) -> list[ResultRow]:
    sheets = compute_sheets(db, a, [m.id for m in members])
    overrides = _overrides(db, a)
    attempts = {
        at.user_id: at
        for at in db.scalars(select(AssessmentAttempt).where(AssessmentAttempt.assessment_id == a.id))
    }
    rows = []
    for m in members:
        sheet, override, attempt = sheets[m.id], overrides.get(m.id), attempts.get(m.id)
        manual = override.override_marks if override else None
        rows.append(
            ResultRow(
                user_id=m.id, name=m.name, email=m.email, status=_result_status(a, attempt, sheet, now),
                tab_switches=attempt.tab_switches if attempt else 0,
                per_problem=[_score_out(p) for p in sheet.per_problem],
                auto_marks=sheet.auto_marks, override_marks=manual,
                final_marks=manual if manual is not None else sheet.auto_marks,
                comment=override.comment if override else None,
                pending=sheet.pending, judge_errors=sheet.judge_errors,
            )
        )
    return rows


def _prepare_results(db: Session, a: Assessment, now, finalizer: Finalizer) -> list[ResultRow]:
    finalize_all(db, a, now, finalizer)
    # Answers that were queued but never judged (for example the server restarted) get another go.
    stuck = [
        s for s in db.scalars(select(Submission).where(Submission.assessment_id == a.id, Submission.status == "queued"))
        if now - clock.aware(s.created_at) > STUCK_AFTER
    ]
    finalizer.schedule(stuck)
    return _build_rows(db, a, _batch_students(db, a), now)


# ---------------------------------------------------------------- list, create, change, delete
@router.get("/assessments", response_model=list[AssessmentSummary])
def list_assessments(user: User = Depends(participants), db: Session = Depends(get_db)):
    now = clock.utc_now()
    query = select(Assessment).where(Assessment.college_id == user.college_id).order_by(Assessment.starts_at.desc())
    if user.role == Role.student.value:
        mine = select(BatchMember.batch_id).where(BatchMember.user_id == user.id)
        query = query.where(Assessment.is_published.is_(True), Assessment.batch_id.in_(mine))
    items = [a for a in db.scalars(query).all() if user.role == Role.student.value or can_manage(user, a, db)]
    attempts = {}
    if user.role == Role.student.value:
        attempts = {
            at.assessment_id: at for at in db.scalars(select(AssessmentAttempt).where(AssessmentAttempt.user_id == user.id))
        }
    return [_summary(db, a, user, now, attempts.get(a.id)) for a in items]


@router.post("/assessments", response_model=AssessmentOut, status_code=201)
def create_assessment(
    data: AssessmentIn, finalizer: Finalizer = Depends(), user: User = Depends(staff), db: Session = Depends(get_db)
):
    now = clock.utc_now()
    batch = db.get(Batch, data.batch_id)
    if batch is None or not can_access_batch(user, batch, db):
        raise HTTPException(status_code=404, detail="Batch not found.")
    _validate_schedule(data.type, data.starts_at, data.ends_at, data.duration_min, now, creating=True)
    a = Assessment(
        batch_id=batch.id, college_id=batch.college_id, created_by=user.id, title=data.title.strip(),
        description=data.description, type=data.type, starts_at=data.starts_at, ends_at=data.ends_at,
        duration_min=data.duration_min, is_published=False, results_published=False,
    )
    a.problems = _make_problem_rows(db, user, data.problems)
    db.add(a)
    db.commit()
    db.refresh(a)
    return _detail(db, a, user, now, finalizer)


@router.get("/assessments/{assessment_id}", response_model=AssessmentOut)
def get_assessment(
    assessment_id: int, finalizer: Finalizer = Depends(), user: User = Depends(participants), db: Session = Depends(get_db)
):
    a = get_assessment_for(user, assessment_id, db)
    return _detail(db, a, user, clock.utc_now(), finalizer)


@router.patch("/assessments/{assessment_id}", response_model=AssessmentOut)
def update_assessment(
    assessment_id: int, data: AssessmentPatch, finalizer: Finalizer = Depends(),
    user: User = Depends(staff), db: Session = Depends(get_db),
):
    now = clock.utc_now()
    a = get_managed_assessment(user, assessment_id, db)
    active = has_activity(db, a)

    starts = data.starts_at or clock.aware(a.starts_at)
    ends = data.ends_at or clock.aware(a.ends_at)
    duration = data.duration_min if data.duration_min is not None else a.duration_min
    _validate_schedule(a.type, starts, ends, duration, now, creating=False)

    if data.problems is not None:
        if active:
            raise HTTPException(status_code=409, detail="Students have already started, so the problems cannot be changed.")
        new_rows = _make_problem_rows(db, user, data.problems)  # checked first, so a mistake changes nothing
        a.problems.clear()
        db.flush()  # remove the old rows BEFORE adding new ones, or a kept problem breaks the "used once" rule
        a.problems.extend(new_rows)
    if data.is_published is False and a.is_published and active:
        raise HTTPException(status_code=409, detail="Students have already started, so it cannot be hidden again.")

    if data.title is not None:
        a.title = data.title.strip()
    if data.description is not None:
        a.description = data.description
    a.starts_at, a.ends_at, a.duration_min = starts, ends, duration
    if data.is_published is not None:
        a.is_published = data.is_published
    publishing_results = data.results_published is True and not a.results_published
    if data.results_published is not None:
        a.results_published = data.results_published
    db.commit()
    db.refresh(a)
    if publishing_results:
        finalize_all(db, a, now, finalizer)  # make sure every saved draft is counted before marks go public
    return _detail(db, a, user, now, finalizer)


@router.delete("/assessments/{assessment_id}", status_code=204)
def delete_assessment(assessment_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    a = get_managed_assessment(user, assessment_id, db)
    if has_activity(db, a):
        raise HTTPException(status_code=409, detail="Students have already started, so it cannot be deleted.")
    db.delete(a)
    db.commit()


# ---------------------------------------------------------------- the student's exam
@router.post("/assessments/{assessment_id}/start", response_model=AssessmentOut)
def start_exam(
    assessment_id: int, finalizer: Finalizer = Depends(), user: User = Depends(students), db: Session = Depends(get_db)
):
    now = clock.utc_now()
    a = get_assessment_for(user, assessment_id, db)
    if a.type != EXAM:
        raise HTTPException(status_code=400, detail="Assignments do not need to be started.")
    if get_attempt(db, a.id, user.id) is None:
        if now < clock.aware(a.starts_at):
            raise HTTPException(status_code=403, detail="The exam has not started yet.")
        if now >= clock.aware(a.ends_at):
            raise HTTPException(status_code=403, detail="The exam is over. You can no longer start it.")
        db.add(AssessmentAttempt(
            assessment_id=a.id, user_id=user.id, started_at=now, deadline_at=personal_deadline(a, now),
        ))
        db.commit()
    return _detail(db, a, user, now, finalizer)  # starting twice just shows the same running exam


@router.post("/assessments/{assessment_id}/finish", response_model=AssessmentOut)
def finish_exam(
    assessment_id: int, finalizer: Finalizer = Depends(), user: User = Depends(students), db: Session = Depends(get_db)
):
    now = clock.utc_now()
    a = get_assessment_for(user, assessment_id, db)
    attempt = get_attempt(db, a.id, user.id)
    if a.type != EXAM or attempt is None:
        raise HTTPException(status_code=409, detail="You have not started this exam.")
    if attempt.finished_at is None:
        attempt.finished_at = min(now, clock.aware(attempt.deadline_at))
        db.commit()
    return _detail(db, a, user, now, finalizer)  # _detail submits any saved but unsent code


@router.post("/assessments/{assessment_id}/tab-switch", status_code=204)
def record_tab_switch(assessment_id: int, user: User = Depends(students), db: Session = Depends(get_db)):
    """The page tells us when the student leaves the exam tab. We only count it. We never block anyone."""
    a = get_assessment_for(user, assessment_id, db)
    attempt = get_attempt(db, a.id, user.id)
    if attempt is not None and attempt_active(attempt, clock.utc_now()):
        attempt.tab_switches += 1
        db.commit()


def _visible_problem(db: Session, user: User, a: Assessment, problem_id: int, now) -> Problem:
    if problem_id not in {ap.problem_id for ap in a.problems}:
        raise HTTPException(status_code=404, detail="This problem is not part of the assessment.")
    if user.role not in STAFF_ROLES:
        if not student_sees_problems(a, get_attempt(db, a.id, user.id), now):
            detail = "The questions appear when the assignment starts." if a.type == ASSIGNMENT else "Press Start to see the questions."
            raise HTTPException(status_code=403, detail=detail)
    return db.get(Problem, problem_id)


@router.get("/assessments/{assessment_id}/problems/{problem_id}", response_model=ProblemOut)
def get_assessment_problem(
    assessment_id: int, problem_id: int, user: User = Depends(participants), db: Session = Depends(get_db)
):
    a = get_assessment_for(user, assessment_id, db)
    return present_problem(_visible_problem(db, user, a, problem_id, clock.utc_now()), user)


@router.get("/assessments/{assessment_id}/problems/{problem_id}/submissions", response_model=list[SubmissionBrief])
def my_assessment_submissions(
    assessment_id: int, problem_id: int, user: User = Depends(students), db: Session = Depends(get_db)
):
    a = get_assessment_for(user, assessment_id, db)
    _visible_problem(db, user, a, problem_id, clock.utc_now())
    subs = db.scalars(
        select(Submission)
        .where(Submission.assessment_id == a.id, Submission.user_id == user.id,
               Submission.problem_id == problem_id, Submission.kind == "submit")
        .order_by(Submission.created_at.desc(), Submission.id.desc()).limit(20)
    ).all()
    out = []
    for sub in subs:
        brief = SubmissionBrief.model_validate(sub)
        if exam_results_hidden(sub, user, db):
            brief = brief.model_copy(update=dict(verdict=None, passed_count=None, total_count=None, runtime_ms=None, hidden=True))
        out.append(brief)
    return out


@router.put("/assessments/{assessment_id}/problems/{problem_id}/draft", response_model=DraftOut)
def save_draft(
    assessment_id: int, problem_id: int, data: DraftIn, user: User = Depends(students), db: Session = Depends(get_db)
):
    """Autosave during an exam. If time runs out, the last saved code is submitted for the student."""
    now = clock.utc_now()
    a = get_assessment_for(user, assessment_id, db)
    if a.type != EXAM:
        raise HTTPException(status_code=400, detail="Drafts are only saved for exams.")
    if problem_id not in {ap.problem_id for ap in a.problems}:
        raise HTTPException(status_code=404, detail="This problem is not part of the assessment.")
    if not attempt_active(get_attempt(db, a.id, user.id), now):
        raise HTTPException(status_code=403, detail="Your time is over. No more answers can be saved.")
    if len(data.source_code.encode("utf-8")) > get_settings().max_source_bytes:
        raise HTTPException(status_code=422, detail="Your code is too long.")
    draft = db.scalar(
        select(AssessmentDraft).where(
            AssessmentDraft.assessment_id == a.id, AssessmentDraft.user_id == user.id, AssessmentDraft.problem_id == problem_id
        )
    )
    if draft is None:
        draft = AssessmentDraft(assessment_id=a.id, user_id=user.id, problem_id=problem_id)
        db.add(draft)
    draft.language, draft.source_code, draft.updated_at = data.language, data.source_code, now
    db.commit()
    return DraftOut(language=draft.language, source_code=draft.source_code, updated_at=draft.updated_at)


@router.get("/assessments/{assessment_id}/problems/{problem_id}/draft", response_model=DraftOut | None)
def get_draft(assessment_id: int, problem_id: int, user: User = Depends(students), db: Session = Depends(get_db)):
    a = get_assessment_for(user, assessment_id, db)
    draft = db.scalar(
        select(AssessmentDraft).where(
            AssessmentDraft.assessment_id == a.id, AssessmentDraft.user_id == user.id, AssessmentDraft.problem_id == problem_id
        )
    )
    return None if draft is None else DraftOut(language=draft.language, source_code=draft.source_code, updated_at=draft.updated_at)


@router.get("/assessments/{assessment_id}/my-result", response_model=MyResultOut)
def my_result(
    assessment_id: int, finalizer: Finalizer = Depends(), user: User = Depends(students), db: Session = Depends(get_db)
):
    now = clock.utc_now()
    a = get_assessment_for(user, assessment_id, db)
    attempt = get_attempt(db, a.id, user.id)
    if attempt is not None and needs_finalize(a, attempt, now):
        finalizer.schedule(finalize_attempt(db, a, attempt, now))
    if not student_may_see_marks(a):
        return MyResultOut(visible=False, total_marks=total_marks(a), auto_marks=None, final_marks=None,
                           comment=None, per_problem=[], pending=0)
    sheet = compute_sheets(db, a, [user.id])[user.id]
    override = _overrides(db, a).get(user.id) if student_may_see_final(a) else None
    manual = override.override_marks if override else None
    return MyResultOut(
        visible=True, total_marks=total_marks(a), auto_marks=sheet.auto_marks,
        final_marks=(manual if manual is not None else sheet.auto_marks) if student_may_see_final(a) else None,
        comment=override.comment if override else None,
        per_problem=[_score_out(p) for p in sheet.per_problem], pending=sheet.pending,
    )


# ---------------------------------------------------------------- results, marks, export (teachers)
@router.get("/assessments/{assessment_id}/results", response_model=ResultsOut)
def get_results(
    assessment_id: int, finalizer: Finalizer = Depends(), user: User = Depends(staff), db: Session = Depends(get_db)
):
    now = clock.utc_now()
    a = get_managed_assessment(user, assessment_id, db)
    rows = _prepare_results(db, a, now, finalizer)
    info = _problem_info(db, a)
    return ResultsOut(
        assessment_id=a.id, title=a.title, type=a.type, results_published=a.results_published, total_marks=total_marks(a),
        problems=[
            AssessmentProblemOut(problem_id=ap.problem_id, title=info[ap.problem_id].title,
                                 difficulty=info[ap.problem_id].difficulty, marks=ap.marks, position=ap.position)
            for ap in a.problems
        ],
        rows=rows, pending_total=sum(r.pending for r in rows), judge_errors_total=sum(r.judge_errors for r in rows),
    )


@router.put("/assessments/{assessment_id}/results/{user_id}", response_model=ResultRow)
def set_override(
    assessment_id: int, user_id: int, data: OverrideIn, user: User = Depends(staff), db: Session = Depends(get_db)
):
    now = clock.utc_now()
    a = get_managed_assessment(user, assessment_id, db)
    member = next((m for m in _batch_students(db, a) if m.id == user_id), None)
    if member is None:
        raise HTTPException(status_code=404, detail="Student not found in this batch.")
    if data.override_marks is not None and data.override_marks > total_marks(a):
        raise HTTPException(status_code=422, detail=f"The marks cannot be more than the total ({total_marks(a)}).")
    comment = (data.comment or "").strip() or None
    row = db.scalar(select(AssessmentResult).where(AssessmentResult.assessment_id == a.id, AssessmentResult.user_id == user_id))
    if data.override_marks is None and comment is None:
        if row is not None:
            db.delete(row)
    else:
        if row is None:
            row = AssessmentResult(assessment_id=a.id, user_id=user_id, updated_by=user.id)
            db.add(row)
        row.override_marks, row.comment, row.updated_by = data.override_marks, comment, user.id
    db.commit()
    return _build_rows(db, a, [member], now)[0]


@router.post("/assessments/{assessment_id}/rejudge")
def rejudge(
    assessment_id: int, finalizer: Finalizer = Depends(), user: User = Depends(staff), db: Session = Depends(get_db)
):
    """Judge again the answers the judge could not check (for example while the judge server was down)."""
    a = get_managed_assessment(user, assessment_id, db)
    if not finalizer.can_judge:
        raise HTTPException(status_code=503, detail="The code judge is not set up. Check JUDGE_BACKEND.")
    failed = db.scalars(select(Submission).where(Submission.assessment_id == a.id, Submission.status == "error")).all()
    for sub in failed:
        sub.status, sub.verdict, sub.message, sub.finished_at = "queued", None, None, None
    db.commit()
    finalizer.schedule(failed)
    return {"requeued": len(failed)}


def csv_safe(value) -> str:
    """Spreadsheets run text that starts with = + - @ as a formula. Names and comments come from users, so defuse them."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


@router.get("/assessments/{assessment_id}/export")
def export_results(
    assessment_id: int, finalizer: Finalizer = Depends(), user: User = Depends(staff), db: Session = Depends(get_db)
):
    now = clock.utc_now()
    a = get_managed_assessment(user, assessment_id, db)
    rows = _prepare_results(db, a, now, finalizer)
    info = _problem_info(db, a)
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(
        ["Name", "Email", "Status"]
        + [csv_safe(f"{info[ap.problem_id].title} (/{ap.marks:g})") for ap in a.problems]
        + [f"Automatic marks (/{total_marks(a):g})", "Final marks", "Teacher comment", "Tab switches"]
    )
    for r in rows:
        writer.writerow(
            [csv_safe(r.name), csv_safe(r.email), r.status]
            + [p.marks for p in r.per_problem]
            + [r.auto_marks, r.final_marks, csv_safe(r.comment), r.tab_switches]
        )
    return Response(
        content="\ufeff" + out.getvalue(),  # the BOM makes Excel read names in any language correctly
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="assessment-{a.id}-results.csv"'},
    )
