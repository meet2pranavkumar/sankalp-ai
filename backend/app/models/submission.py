from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Submission(Base):
    """One 'Run' (try the code on my own input) or one 'Submit' (judge against all test cases)."""

    __tablename__ = "submissions"
    __table_args__ = (Index("ix_submissions_user_problem", "user_id", "problem_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    problem_id: Mapped[int | None] = mapped_column(ForeignKey("problems.id"), index=True)  # a Run may have no problem
    kind: Mapped[str] = mapped_column(String(10), nullable=False)  # "run" or "submit"
    language: Mapped[str] = mapped_column(String(10), nullable=False)
    source_code: Mapped[str] = mapped_column(Text, nullable=False)
    stdin: Mapped[str | None] = mapped_column(Text)  # only for Run

    # queued -> running -> done (or error if the judge itself failed)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="queued", index=True)
    # submit: accepted, wrong_answer, time_limit, runtime_error, compile_error, internal_error
    # run:    ok, time_limit, runtime_error, compile_error, internal_error
    verdict: Mapped[str | None] = mapped_column(String(20))
    passed_count: Mapped[int | None] = mapped_column(Integer)
    total_count: Mapped[int | None] = mapped_column(Integer)
    runtime_ms: Mapped[int | None] = mapped_column(Integer)
    memory_kb: Mapped[int | None] = mapped_column(Integer)
    stdout: Mapped[str | None] = mapped_column(Text)
    stderr: Mapped[str | None] = mapped_column(Text)
    compile_output: Mapped[str | None] = mapped_column(Text)
    message: Mapped[str | None] = mapped_column(Text)
    results: Mapped[list | None] = mapped_column(JSON)  # per test case, hidden ones without data

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
