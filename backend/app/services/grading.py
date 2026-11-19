"""Decides the verdict. Pure functions: no database, no network, easy to test."""
from dataclasses import dataclass, field

from app.services.judge.base import JudgeOutcome, RunStatus

ACCEPTED = "accepted"
WRONG_ANSWER = "wrong_answer"
TIME_LIMIT = "time_limit"
RUNTIME_ERROR = "runtime_error"
COMPILE_ERROR = "compile_error"
INTERNAL_ERROR = "internal_error"

SHOW_LIMIT = 2000  # characters of input/output shown for sample tests


def normalize(text: str) -> str:
    """Compare outputs fairly: ignore \\r\\n vs \\n, spaces at line ends, and blank lines at the end."""
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def judge_verdict(outcome: JudgeOutcome, expected_output: str) -> str:
    if outcome.status == RunStatus.compile_error:
        return COMPILE_ERROR
    if outcome.status == RunStatus.internal_error:
        return INTERNAL_ERROR
    if outcome.status == RunStatus.time_limit:
        return TIME_LIMIT
    if outcome.status == RunStatus.runtime_error:
        return RUNTIME_ERROR
    return ACCEPTED if normalize(outcome.stdout) == normalize(expected_output) else WRONG_ANSWER


@dataclass
class TestData:
    __test__ = False
    input: str
    expected_output: str
    is_hidden: bool
    weight: int = 1


@dataclass
class GradeResult:
    verdict: str
    passed: int
    total: int
    runtime_ms: int
    memory_kb: int
    compile_output: str = ""
    message: str = ""
    results: list[dict] = field(default_factory=list)


def _cut(text: str) -> str:
    return text if len(text) <= SHOW_LIMIT else text[:SHOW_LIMIT] + "\n… (cut)"


def grade(tests: list[TestData], outcomes: list[JudgeOutcome]) -> GradeResult:
    total = len(tests)
    runtime = max((o.time_ms for o in outcomes), default=0)
    memory = max((o.memory_kb for o in outcomes), default=0)

    # A compile error is the same for every test: report it once.
    for o in outcomes:
        if o.status == RunStatus.compile_error:
            return GradeResult(COMPILE_ERROR, 0, total, 0, 0, compile_output=o.compile_output or o.message)

    # If the judge itself failed, do not blame the student's code.
    for o in outcomes:
        if o.status == RunStatus.internal_error:
            return GradeResult(INTERNAL_ERROR, 0, total, runtime, memory, message=o.message)

    results: list[dict] = []
    verdicts: list[str] = []
    for position, (test, outcome) in enumerate(zip(tests, outcomes), start=1):
        verdict = judge_verdict(outcome, test.expected_output)
        verdicts.append(verdict)
        entry = {
            "position": position,
            "verdict": verdict,
            "time_ms": outcome.time_ms,
            "memory_kb": outcome.memory_kb,
            "hidden": test.is_hidden,
        }
        if not test.is_hidden:  # students may see sample tests in full, hidden ones never
            entry.update(
                input=_cut(test.input),
                expected=_cut(test.expected_output),
                actual=_cut(outcome.stdout),
                error=_cut(outcome.stderr or outcome.message),
            )
        results.append(entry)

    passed = sum(1 for v in verdicts if v == ACCEPTED)
    overall = next((v for v in verdicts if v != ACCEPTED), ACCEPTED)
    return GradeResult(overall, passed, total, runtime, memory, results=results)
