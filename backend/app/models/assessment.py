from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Assessment(Base):
    """An assignment (open for days) or an exam (each student gets a timer) for one batch."""

    __tablename__ = "assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id"), index=True, nullable=False)
    college_id: Mapped[int] = mapped_column(ForeignKey("colleges.id"), index=True, nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    type: Mapped[str] = mapped_column(String(12), nullable=False)  # "assignment" or "exam"
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_min: Mapped[int | None] = mapped_column(Integer)  # exams only: minutes each student gets
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # students can see it
    results_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Assignments only: may students use the AI helper? Exams never allow it, whatever this says.
    ai_hints_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    problems = relationship(
        "AssessmentProblem", order_by="AssessmentProblem.position", cascade="all, delete-orphan", lazy="selectin"
    )


class AssessmentProblem(Base):
    __tablename__ = "assessment_problems"
    __table_args__ = (UniqueConstraint("assessment_id", "problem_id", name="uq_assessment_problem"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("assessments.id", ondelete="CASCADE"), index=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id"), index=True)
    marks: Mapped[float] = mapped_column(Float, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)


class AssessmentAttempt(Base):
    """A student's one try at an exam. The server keeps the clock, not the browser."""

    __tablename__ = "assessment_attempts"
    __table_args__ = (UniqueConstraint("assessment_id", "user_id", name="uq_attempt_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("assessments.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # saved drafts were submitted
    tab_switches: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # recorded only, never blocks


class AssessmentDraft(Base):
    """The last code a student saved for an exam problem. Submitted for them when time ends."""

    __tablename__ = "assessment_drafts"
    __table_args__ = (UniqueConstraint("assessment_id", "user_id", "problem_id", name="uq_draft"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("assessments.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id"))
    language: Mapped[str] = mapped_column(String(10), nullable=False)
    source_code: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class AssessmentResult(Base):
    """Only what a teacher changed by hand. The automatic marks are always worked out fresh from the submissions."""

    __tablename__ = "assessment_results"
    __table_args__ = (UniqueConstraint("assessment_id", "user_id", name="uq_result_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("assessments.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    override_marks: Mapped[float | None] = mapped_column(Float)
    comment: Mapped[str | None] = mapped_column(Text)
    updated_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
