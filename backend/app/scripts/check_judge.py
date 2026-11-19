"""Checks that your code judge really works and really protects you.

Run from the backend folder, after setting JUDGE_BACKEND in .env:
    python -m app.scripts.check_judge

Every line should say PASS (SKIP is fine for a language you do not use).
If "Network is blocked" or "Infinite loop is stopped" says FAIL, do NOT let students use this judge.
"""
import sys
from dataclasses import dataclass
from typing import Callable

from app.services.judge.base import Judge, JudgeJob, JudgeOutcome, RunStatus

NETWORK_PROBE = """
import socket
try:
    socket.create_connection(("1.1.1.1", 53), timeout=2).close()
    print("CONNECTED")
except Exception:
    print("BLOCKED")
"""


@dataclass
class Probe:
    name: str
    job: JudgeJob
    passes: Callable[[JudgeOutcome], bool]
    why_it_matters: str = ""


def _stdout_is(text: str):
    return lambda o: o.status == RunStatus.ok and o.stdout.strip() == text


def _stopped(o: JudgeOutcome) -> bool:
    return o.status in (RunStatus.time_limit, RunStatus.runtime_error)


def build_probes() -> list[Probe]:
    return [
        Probe("Python runs", JudgeJob("python", 'print("hello")'), _stdout_is("hello")),
        Probe("C runs", JudgeJob("c", '#include <stdio.h>\nint main(){puts("hello");return 0;}'), _stdout_is("hello")),
        Probe("C++ runs", JudgeJob("cpp", '#include <iostream>\nint main(){std::cout<<"hello";}'), _stdout_is("hello")),
        Probe(
            "Java runs",
            JudgeJob("java", 'public class Main{public static void main(String[] a){System.out.println("hello");}}', time_limit_ms=2000),
            _stdout_is("hello"),
        ),
        Probe("Input is read", JudgeJob("python", "print(int(input()) * 2)", stdin="21\n"), _stdout_is("42")),
        Probe("Compile error is detected", JudgeJob("c", "int main( {"), lambda o: o.status == RunStatus.compile_error),
        Probe("Crash is detected", JudgeJob("python", "raise SystemExit(3)"), lambda o: o.status == RunStatus.runtime_error),
        Probe(
            "Infinite loop is stopped",
            JudgeJob("python", "while True:\n    pass", time_limit_ms=500),
            lambda o: o.status == RunStatus.time_limit,
            "Without this, one bad program can freeze the whole server.",
        ),
        Probe(
            "Memory hog is stopped",
            JudgeJob("python", "x = bytearray(3 * 1024**3)\nprint(len(x))", memory_limit_mb=64),
            _stopped,
            "Without this, one program can use all the server memory.",
        ),
        Probe(
            "Output flood is stopped",
            JudgeJob("python", "while True:\n    print('x' * 1000)", time_limit_ms=1000),
            _stopped,
            "Without this, one program can fill the disk.",
        ),
        Probe(
            "Network is blocked",
            JudgeJob("python", NETWORK_PROBE),
            _stdout_is("BLOCKED"),
            "Without this, student code could attack other computers from your server.",
        ),
    ]


def run_checks(judge: Judge) -> list[tuple[str, str, str]]:
    """Returns (status, name, detail) for every probe. status is PASS, FAIL or SKIP."""
    probes = build_probes()
    outcomes = judge.run_jobs([p.job for p in probes])
    rows = []
    for probe, o in zip(probes, outcomes):
        missing = o.status == RunStatus.internal_error and "not installed" in o.message
        if missing:
            rows.append(("SKIP", probe.name, o.message))
        elif probe.passes(o):
            rows.append(("PASS", probe.name, f"{o.time_ms} ms"))
        else:
            detail = f"got {o.status.value}"
            extra = (o.message or o.compile_output or o.stderr or o.stdout).strip().replace("\n", " ")[:100]
            if extra:
                detail += f": {extra}"
            if probe.why_it_matters:
                detail += f"  <- {probe.why_it_matters}"
            rows.append(("FAIL", probe.name, detail))
    return rows


def main() -> int:
    from app.core.config import get_settings
    from app.services.judge import get_judge

    settings = get_settings()
    print(f"Judge backend: {settings.judge_backend}")
    if settings.judge_backend == "judge0":
        print(f"Judge0 address: {settings.judge0_url}")
    elif settings.judge_backend == "local":
        print("WARNING: the local judge has NO sandbox. It is for development only.")
    try:
        rows = run_checks(get_judge())
    except RuntimeError as err:
        print(f"Cannot start the judge: {err}")
        return 2

    width = max(len(name) for _, name, _ in rows)
    for status, name, detail in rows:
        print(f"  {status:4}  {name:<{width}}  {detail}")
    failed = [r for r in rows if r[0] == "FAIL"]
    print()
    if failed:
        print(f"{len(failed)} check(s) FAILED. Fix them before real students use this judge.")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
