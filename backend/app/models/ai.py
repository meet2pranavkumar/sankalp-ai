from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AIRequest(Base):
    """Every hint or error explanation a student asked for. Teachers use this to see where students get stuck."""

    __tablename__ = "ai_requests"
    __table_args__ = (Index("ix_ai_user_problem_time", "user_id", "problem_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)  # "hint" or "explain"
    level: Mapped[int | None] = mapped_column(Integer)  # hints only: 1, 2 or 3
    language: Mapped[str] = mapped_column(String(10), nullable=False)
    # ok = the AI answer was shown | fallback = the AI tried to give code, a safe text was shown instead
    # error = the AI service failed (this request does not use up the student's daily hints)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    response_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    flagged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # the AI answer looked like a solution
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
