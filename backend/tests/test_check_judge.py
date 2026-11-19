import shutil

import pytest

from app.scripts.check_judge import run_checks
from app.services.judge.base import JudgeOutcome, RunStatus
from app.services.judge.local import LocalJudge


def by_name(rows):
    return {name: status for status, name, _ in rows}


def test_a_judge_that_blindly_says_ok_is_caught(fake_judge):
    """A broken or fake judge must NOT pass the self-test."""
    fake_judge.respond = lambda job: JudgeOutcome(status=RunStatus.ok, stdout="hello\n")
    results = by_name(run_checks(fake_judge))
    assert results["Compile error is detected"] == "FAIL"
    assert results["Infinite loop is stopped"] == "FAIL"
    assert results["Network is blocked"] == "FAIL"
    assert results["Python runs"] == "PASS"


def test_missing_compilers_are_skipped_not_failed(fake_judge):
    fake_judge.respond = lambda job: JudgeOutcome(status=RunStatus.internal_error, message="javac (JDK) is not installed here")
    assert set(by_name(run_checks(fake_judge)).values()) == {"SKIP"}


def test_other_judge_errors_are_failures(fake_judge):
    fake_judge.respond = lambda job: JudgeOutcome(status=RunStatus.internal_error, message="The code judge is not reachable")
    assert set(by_name(run_checks(fake_judge)).values()) == {"FAIL"}


@pytest.mark.skipif(shutil.which("gcc") is None, reason="gcc not installed")
def test_local_judge_passes_the_safety_checks_it_can_pass():
    results = by_name(run_checks(LocalJudge()))
    for name in ("Python runs", "C runs", "Input is read", "Compile error is detected", "Crash is detected",
                 "Infinite loop is stopped", "Memory hog is stopped", "Output flood is stopped"):
        assert results[name] == "PASS", name
