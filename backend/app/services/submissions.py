"""Background work: send a submission to the judge and save what came back."""
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import sessionmaker

from app.models import Problem, Submission
from app.services.grading import INTERNAL_ERROR, TestData, grade
from app.services.judge.base import Judge, JudgeJob, RunStatus

log = logging.getLogger(__name__)

DEFAULT_RUN_LIMIT_MS = 2000
DEFAULT_RUN_MEMORY_MB = 256
KEEP_CHARS = 20000  # most output we store for a Run


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def process_submission(submission_id: int, session_factory: sessionmaker, judge: Judge) -> None:
    with session_factory() as db:
        sub = db.get(Submission, submission_id)
        if sub is None or sub.status != "queued":
            return
        sub.status = "running"
        db.commit()
        try:
            if sub.kind == "run":
                _process_run(db, sub, judge)
            else:
                _process_submit(db, sub, judge)
        except Exception:
            log.exception("Judging submission %s failed", submission_id)
            db.rollback()
            sub = db.get(Submission, submission_id)
            sub.status = "error"
            sub.verdict = INTERNAL_ERROR
            sub.message = "Something went wrong while judging. Please try again."
            sub.finished_at = _utc_now()
        db.commit()


def _process_run(db, sub: Submission, judge: Judge) -> None:
    problem = db.get(Problem, sub.problem_id) if sub.problem_id else None
    job = JudgeJob(
        language=sub.language,
        source_code=sub.source_code,
        stdin=sub.stdin or "",
        time_limit_ms=problem.time_limit_ms if problem else DEFAULT_RUN_LIMIT_MS,
        memory_limit_mb=problem.memory_limit_mb if problem else DEFAULT_RUN_MEMORY_MB,
    )
    outcome = judge.run_jobs([job])[0]
    sub.verdict = outcome.status.value
    sub.stdout = outcome.stdout[:KEEP_CHARS]
    sub.stderr = outcome.stderr[:KEEP_CHARS]
    sub.compile_output = outcome.compile_output[:KEEP_CHARS]
    sub.message = outcome.message
    sub.runtime_ms = outcome.time_ms
    sub.memory_kb = outcome.memory_kb
    sub.status = "error" if outcome.status == RunStatus.internal_error else "done"
    sub.finished_at = _utc_now()


def _process_submit(db, sub: Submission, judge: Judge) -> None:
    problem = db.get(Problem, sub.problem_id)
    tests = list(problem.test_cases)
    jobs = [
        JudgeJob(
            language=sub.language,
            source_code=sub.source_code,
            stdin=t.input,
            time_limit_ms=problem.time_limit_ms,
            memory_limit_mb=problem.memory_limit_mb,
        )
        for t in tests
    ]
    outcomes = judge.run_jobs(jobs)
    result = grade([TestData(t.input, t.expected_output, t.is_hidden, t.weight) for t in tests], outcomes)

    sub.verdict = result.verdict
    sub.passed_count = result.passed
    sub.total_count = result.total
    sub.runtime_ms = result.runtime_ms
    sub.memory_kb = result.memory_kb
    sub.compile_output = result.compile_output[:KEEP_CHARS]
    sub.message = result.message
    sub.results = result.results
    sub.status = "error" if result.verdict == INTERNAL_ERROR else "done"
    sub.finished_at = _utc_now()
