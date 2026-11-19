import pytest

from app.services.grading import (
    ACCEPTED, COMPILE_ERROR, INTERNAL_ERROR, RUNTIME_ERROR, TIME_LIMIT, WRONG_ANSWER,
    TestData, grade, judge_verdict, normalize,
)
from app.services.judge.base import JudgeOutcome, RunStatus


def ok(stdout, ms=10, kb=100):
    return JudgeOutcome(status=RunStatus.ok, stdout=stdout, time_ms=ms, memory_kb=kb)


@pytest.mark.parametrize(
    "a,b",
    [
        ("42\n", "42"),
        ("42\r\n", "42\n"),
        ("1 2 3   \n4 5\n\n\n", "1 2 3\n4 5"),
        ("", "\n\n"),
    ],
)
def test_outputs_that_should_match(a, b):
    assert normalize(a) == normalize(b)


@pytest.mark.parametrize(
    "a,b",
    [("42", "43"), ("1 2", "1  2"), ("a\nb", "a b"), (" 5", "5"), ("a\n\nb", "a\nb")],
)
def test_outputs_that_should_not_match(a, b):
    assert normalize(a) != normalize(b)


def test_verdict_for_each_outcome_type():
    assert judge_verdict(ok("7\n"), "7") == ACCEPTED
    assert judge_verdict(ok("8\n"), "7") == WRONG_ANSWER
    assert judge_verdict(JudgeOutcome(RunStatus.time_limit), "7") == TIME_LIMIT
    assert judge_verdict(JudgeOutcome(RunStatus.runtime_error), "7") == RUNTIME_ERROR
    assert judge_verdict(JudgeOutcome(RunStatus.compile_error), "7") == COMPILE_ERROR
    assert judge_verdict(JudgeOutcome(RunStatus.internal_error), "7") == INTERNAL_ERROR


def three_tests():
    return [TestData("1", "1", False), TestData("2", "2", True), TestData("3", "3", True)]


def test_all_pass_is_accepted():
    r = grade(three_tests(), [ok("1"), ok("2"), ok("3")])
    assert (r.verdict, r.passed, r.total) == (ACCEPTED, 3, 3)


def test_first_failing_test_decides_the_verdict_but_all_tests_are_counted():
    outcomes = [ok("1"), ok("999"), JudgeOutcome(RunStatus.time_limit, time_ms=1000)]
    r = grade(three_tests(), outcomes)
    assert r.verdict == WRONG_ANSWER  # test 2 failed first
    assert (r.passed, r.total) == (1, 3)
    assert r.runtime_ms == 1000


def test_compile_error_is_reported_once_with_the_compiler_text():
    bad = JudgeOutcome(RunStatus.compile_error, compile_output="main.c:1: error: oops")
    r = grade(three_tests(), [bad, bad, bad])
    assert r.verdict == COMPILE_ERROR
    assert r.compile_output == "main.c:1: error: oops"
    assert (r.passed, r.total) == (0, 3)
    assert r.results == []


def test_judge_failure_is_not_blamed_on_the_student():
    r = grade(three_tests(), [ok("1"), JudgeOutcome(RunStatus.internal_error, message="judge down"), ok("3")])
    assert r.verdict == INTERNAL_ERROR
    assert r.message == "judge down"
    assert r.passed == 0


def test_hidden_tests_never_leak_their_data():
    r = grade(three_tests(), [ok("1"), ok("WRONG"), ok("3")])
    sample, hidden = r.results[0], r.results[1]
    assert sample["input"] == "1" and sample["expected"] == "1" and sample["actual"] == "1"
    assert set(hidden) == {"position", "verdict", "time_ms", "memory_kb", "hidden"}
    assert "WRONG" not in str(hidden) and hidden["verdict"] == WRONG_ANSWER


def test_long_sample_output_is_cut():
    r = grade([TestData("x", "y", False)], [ok("z" * 10_000)])
    assert len(r.results[0]["actual"]) < 2100
