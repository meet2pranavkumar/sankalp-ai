from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Problem(Base):
    __tablename__ = "problems"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # None = belongs to the shared problem bank (made by the platform owner).
    college_id: Mapped[int | None] = mapped_column(ForeignKey("colleges.id"), index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    statement_md: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty: Mapped[str] = mapped_column(String(10), nullable=False, default="easy", index=True)
    tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    time_limit_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)
    memory_limit_mb: Mapped[int] = mapped_column(Integer, nullable=False, default=256)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    test_cases = relationship(
        "TestCase",
        order_by="TestCase.position",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class TestCase(Base):
    __test__ = False  # tell pytest this is not a test class
    __tablename__ = "test_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    input: Mapped[str] = mapped_column(Text, nullable=False, default="")
    expected_output: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    weight: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
