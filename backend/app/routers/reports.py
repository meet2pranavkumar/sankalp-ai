import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import clock
from app.core.access import can_access_batch
from app.core.csvutil import csv_safe
from app.core.database import get_db
from app.core.deps import require_roles
from app.models import Batch, BatchMember, Role, User
from app.schemas import BatchReportOut, BatchSummaryOut, StudentReportOut
from app.services.reports import (
    ai_requests_in_last_30_days, batch_report, batch_summary, local_date, student_report,
)

router = APIRouter(prefix="/reports", tags=["reports"])
students_only = require_roles(Role.student)
staff = require_roles(Role.teacher, Role.admin)

InactiveDays = Query(default=7, ge=1, le=365, description="A student with no activity for this many days is shown as inactive")


def _batches_for(db: Session, user: User) -> list[Batch]:
    """Teachers: the batches they made. Admins: every batch of the college."""
    query = select(Batch).where(Batch.college_id == user.college_id).order_by(Batch.year.desc(), func.lower(Batch.name), Batch.id)
    if user.role == Role.teacher.value:
        query = query.where(Batch.created_by == user.id)
    return db.scalars(query).all()


def _batch_or_404(db: Session, user: User, batch_id: int) -> Batch:
    batch = db.get(Batch, batch_id)
    if batch is None or not can_access_batch(user, batch, db):
        raise HTTPException(status_code=404, detail="Batch not found.")
    return batch


def _student_in_scope(db: Session, user: User, student: User | None) -> bool:
    if student is None or student.role != Role.student.value or student.college_id != user.college_id:
        return False
    if user.role == Role.admin.value:
        return True
    return db.scalar(
        select(BatchMember.id)
        .join(Batch, Batch.id == BatchMember.batch_id)
        .where(BatchMember.user_id == student.id, Batch.created_by == user.id, Batch.college_id == user.college_id)
        .limit(1)
    ) is not None


# ---------------------------------------------------------------- students
@router.get("/me", response_model=StudentReportOut)
def my_progress(user: User = Depends(students_only), db: Session = Depends(get_db)):
    """The student's own dashboard. Exam results stay hidden here until the teacher publishes them."""
    return student_report(db, user, clock.utc_now(), hide_secret=True)


# ---------------------------------------------------------------- teachers and admins
@router.get("/batches", response_model=list[BatchSummaryOut])
def batches(inactive_days: int = InactiveDays, user: User = Depends(staff), db: Session = Depends(get_db)):
    now = clock.utc_now()
    return [batch_summary(db, b, now, inactive_days) for b in _batches_for(db, user)]


@router.get("/batches/{batch_id}", response_model=BatchReportOut)
def batch_detail(batch_id: int, inactive_days: int = InactiveDays, user: User = Depends(staff), db: Session = Depends(get_db)):
    return batch_report(db, _batch_or_404(db, user, batch_id), clock.utc_now(), inactive_days)


@router.get("/batches/{batch_id}/export")
def export_batch(batch_id: int, inactive_days: int = InactiveDays, user: User = Depends(staff), db: Session = Depends(get_db)):
    batch = _batch_or_404(db, user, batch_id)
    report = batch_report(db, batch, clock.utc_now(), inactive_days)
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow([
        "Name", "Email", "Lessons completed", "Lessons in courses", "Completion %", "Problems solved",
        "Submissions (30 days)", "AI helper requests (30 days)", "Last active", "Days since last activity", "Status",
    ])
    for r in report.students:
        writer.writerow([
            csv_safe(r.name), csv_safe(r.email), r.lessons_completed, r.lessons_total, r.completion_percent, r.problems_solved,
            r.submissions_30d, r.ai_requests_30d, local_date(r.last_active_at).isoformat() if r.last_active_at else "Never",
            "" if r.days_inactive is None else r.days_inactive, r.status,
        ])
    return Response(
        content="\ufeff" + out.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="batch-{batch.id}-progress.csv"'},
    )


@router.get("/students/{user_id}", response_model=StudentReportOut)
def student_detail(user_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    """One student's dashboard, as the teacher sees it: real exam results, and how often they used the AI helper."""
    student = db.get(User, user_id)
    if not _student_in_scope(db, user, student):
        raise HTTPException(status_code=404, detail="Student not found.")
    now = clock.utc_now()
    report = student_report(db, student, now, hide_secret=False)
    report.ai_requests_30d = ai_requests_in_last_30_days(db, student.id, now)
    return report
