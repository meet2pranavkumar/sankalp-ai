"""Lets request handlers start judging in the background, without failing if the judge is not set up."""
from fastapi import BackgroundTasks, Depends
from sqlalchemy.orm import sessionmaker

from app.core.database import get_session_factory
from app.services.judge import Judge, get_judge
from app.services.submissions import process_submission


def optional_judge() -> Judge | None:
    """The judge, or None if it is not set up. Reading an exam page must never fail because of that."""
    try:
        return get_judge()
    except RuntimeError:
        return None


class Finalizer:
    def __init__(
        self,
        background: BackgroundTasks,
        judge: Judge | None = Depends(optional_judge),
        session_factory: sessionmaker = Depends(get_session_factory),
    ):
        self._background, self._judge, self._factory = background, judge, session_factory

    @property
    def can_judge(self) -> bool:
        return self._judge is not None

    def schedule(self, submissions) -> int:
        """Judge these submissions after the response is sent. Returns how many were scheduled."""
        if self._judge is None:
            return 0
        for sub in submissions:
            self._background.add_task(process_submission, sub.id, self._factory, self._judge)
        return len(submissions)
