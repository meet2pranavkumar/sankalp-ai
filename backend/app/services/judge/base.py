"""The judge is a plug: anything with run_jobs() can run student code."""
from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class RunStatus(str, Enum):
    ok = "ok"  # program finished normally
    compile_error = "compile_error"
    runtime_error = "runtime_error"
    time_limit = "time_limit"
    internal_error = "internal_error"  # the judge itself had a problem, not the student's fault


@dataclass
class JudgeJob:
    language: str  # key from app.services.languages
    source_code: str
    stdin: str = ""
    time_limit_ms: int = 1000
    memory_limit_mb: int = 256


@dataclass
class JudgeOutcome:
    status: RunStatus
    stdout: str = ""
    stderr: str = ""
    compile_output: str = ""
    message: str = ""
    time_ms: int = 0
    memory_kb: int = 0


class Judge(Protocol):
    def run_jobs(self, jobs: list[JudgeJob]) -> list[JudgeOutcome]:
        """Run every job. Always returns one outcome per job, in the same order."""
        ...


def internal_error(message: str) -> JudgeOutcome:
    return JudgeOutcome(status=RunStatus.internal_error, message=message)
