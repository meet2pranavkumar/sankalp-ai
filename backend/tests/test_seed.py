"""Checks the starter course and problems. Every example and every reference solution is really compiled and run."""
import re
import shutil

import pytest

from app.models import Course, Problem
from app.schemas import LessonIn, ProblemIn
from app.seed.blocks import extract_runnables
from app.seed.loader import seed_starter_content
from app.seed.starter_c_course import COURSE
from app.seed.starter_c_problems import PROBLEMS
from app.services.grading import ACCEPTED, TestData, grade
from app.services.judge.base import JudgeJob, RunStatus
from app.services.judge.local import LocalJudge

needs_gcc = pytest.mark.skipif(shutil.which("gcc") is None, reason="gcc not installed")
LESSONS = [(u["title"], l) for u in COURSE["units"] for l in u["lessons"]]


# ---------- the block parser ----------
def test_runnable_blocks_and_their_input_are_found():
    md = "text\n```c run\nint main(){}\n```\n```stdin\n5 7\n```\nmore\n```c\nnot runnable\n```\n```python run\nprint(1)\n```\n"
    found = extract_runnables(md)
    assert [(r.language, r.code.strip(), r.stdin.strip()) for r in found] == [
        ("c", "int main(){}", "5 7"),
        ("python", "print(1)", ""),
    ]


def test_stdin_block_is_only_attached_when_it_directly_follows():
    md = "```c run\nA\n```\n\nSome words in between.\n\n```stdin\n1\n```\n"
    assert extract_runnables(md)[0].stdin == ""


def test_unknown_languages_are_not_runnable():
    assert extract_runnables("```cobol run\nX\n```\n```bash run\nls\n```") == []


# ---------- the course itself ----------
def test_course_is_valid_for_our_own_api_rules():
    assert COURSE["title"] and COURSE["language"] == "c"
    assert len(COURSE["units"]) == 6 and len(LESSONS) == 14
    for unit_title, lesson in LESSONS:
        LessonIn(title=lesson["title"], content_md=lesson["content_md"].strip())  # same limits as the editor
        assert len(lesson["content_md"]) > 500, lesson["title"]


def test_every_lesson_has_runnable_examples_and_a_summary_of_what_to_do_next():
    for _, lesson in LESSONS:
        assert extract_runnables(lesson["content_md"]), f"{lesson['title']} has nothing to run"


def test_practice_lines_point_to_problems_that_exist():
    titles = {p["title"] for p in PROBLEMS}
    mentioned = set()
    for _, lesson in LESSONS:
        for line in re.findall(r"\*\*Practice:\*\*\s*(.+)", lesson["content_md"]):
            for name in line.split(","):
                mentioned.add(name.strip())
    assert mentioned, "no practice lines found"
    assert mentioned <= titles, f"unknown problems: {mentioned - titles}"


def test_lesson_and_unit_titles_are_unique():
    titles = [l["title"] for _, l in LESSONS]
    assert len(titles) == len(set(titles))


@needs_gcc
@pytest.mark.parametrize("unit_title,lesson", LESSONS, ids=[l["title"] for _, l in LESSONS])
def test_every_runnable_example_compiles_and_runs(unit_title, lesson):
    judge = LocalJudge()
    blocks = extract_runnables(lesson["content_md"])
    jobs = [JudgeJob(b.language, b.code, b.stdin, time_limit_ms=2000, memory_limit_mb=128) for b in blocks]
    for block, outcome in zip(blocks, judge.run_jobs(jobs)):
        assert outcome.status == RunStatus.ok, f"{lesson['title']}: {outcome.status} {outcome.compile_output or outcome.stderr}\n{block.code}"
        assert outcome.stdout.strip(), f"{lesson['title']}: example printed nothing\n{block.code}"


# ---------- the practice problems ----------
def test_problems_are_valid_for_our_own_api_rules():
    titles = [p["title"] for p in PROBLEMS]
    assert len(titles) == len(set(titles)) == 15
    for p in PROBLEMS:
        body = ProblemIn(
            title=p["title"], statement_md=p["statement_md"], difficulty=p["difficulty"], tags=p["tags"],
            test_cases=[{"input": i, "expected_output": o, "is_hidden": h} for i, o, h in p["tests"]],
        )
        assert any(not t.is_hidden for t in body.test_cases), f"{p['title']} needs a sample"
        assert p["tests"][0][2] is False, f"{p['title']}: the first test should be the visible sample"


@needs_gcc
@pytest.mark.parametrize("problem", PROBLEMS, ids=[p["title"] for p in PROBLEMS])
def test_reference_solution_passes_every_test(problem):
    judge = LocalJudge()
    jobs = [JudgeJob("c", problem["reference"], inp, time_limit_ms=1000, memory_limit_mb=128) for inp, _, _ in problem["tests"]]
    outcomes = judge.run_jobs(jobs)
    result = grade([TestData(i, o, h) for i, o, h in problem["tests"]], outcomes)
    detail = [(r["position"], r["verdict"]) for r in result.results if r["verdict"] != ACCEPTED]
    assert result.verdict == ACCEPTED, f"{problem['title']}: failing tests {detail} {result.compile_output}"
    assert result.passed == result.total


@needs_gcc
@pytest.mark.parametrize("problem", PROBLEMS, ids=[p["title"] for p in PROBLEMS])
def test_a_lazy_solution_does_not_pass(problem):
    """A program that prints nothing must fail: the tests really check something."""
    judge = LocalJudge()
    lazy = "int main(void){return 0;}"
    outcomes = judge.run_jobs([JudgeJob("c", lazy, inp) for inp, _, _ in problem["tests"]])
    result = grade([TestData(i, o, h) for i, o, h in problem["tests"]], outcomes)
    assert result.verdict != ACCEPTED


# ---------- loading into the database ----------
def test_seeding_creates_a_shared_published_course_and_problems(client, world, login, db_session):
    report = seed_starter_content(db_session, world["super"])
    assert (report.problems_created, report.course_created) == (15, True)
    s = login(world["student2"])  # a student of ANY college can use it
    courses = client.get("/api/v1/courses", headers=s).json()
    assert [(c["title"], c["is_shared"], c["total_lessons"]) for c in courses] == [("C Programming Basics", True, 14)]
    course = client.get(f"/api/v1/courses/{courses[0]['id']}", headers=s).json()
    assert [u["title"] for u in course["units"]][0] == "1. Getting started"
    first = course["units"][0]["lessons"][0]["id"]
    lesson = client.get(f"/api/v1/lessons/{first}", headers=s).json()
    assert lesson["title"] == "Your first C program" and "```c run" in lesson["content_md"]
    assert lesson["prev_lesson_id"] is None and lesson["next_lesson_id"] is not None
    assert len(client.get("/api/v1/problems", headers=s).json()) == 15


def test_students_see_no_hidden_tests_of_seeded_problems(client, world, login, db_session):
    seed_starter_content(db_session, world["super"])
    s = login(world["student1"])
    pid = next(p["id"] for p in client.get("/api/v1/problems?q=Prime", headers=s).json())
    tests = client.get(f"/api/v1/problems/{pid}", headers=s).json()["test_cases"]
    assert len(tests) == 1 and tests[0]["is_hidden"] is False


def test_seeding_twice_adds_nothing_new(world, db_session):
    seed_starter_content(db_session, world["super"])
    again = seed_starter_content(db_session, world["super"])
    assert (again.problems_created, again.problems_existing, again.course_created) == (0, 15, False)
    assert db_session.query(Course).count() == 1 and db_session.query(Problem).count() == 15


def test_draft_seeding_keeps_the_course_hidden_from_students(client, world, login, db_session):
    seed_starter_content(db_session, world["super"], publish=False)
    assert client.get("/api/v1/courses", headers=login(world["student1"])).json() == []
    assert len(client.get("/api/v1/courses", headers=login(world["super"])).json()) == 1


def test_a_teacher_can_copy_the_seeded_course_and_make_it_theirs(client, world, login, db_session):
    seed_starter_content(db_session, world["super"])
    t = login(world["teacher1"])
    shared_id = client.get("/api/v1/courses", headers=t).json()[0]["id"]
    copy = client.post(f"/api/v1/courses/{shared_id}/duplicate", headers=t).json()
    assert copy["can_edit"] and copy["total_lessons"] == 14 and copy["is_published"] is False


# ---------- the command-line script itself ----------
def run_script(monkeypatch, capsys, session_factory, *args):
    import sys

    from app.scripts import seed_starter_course

    monkeypatch.setattr(seed_starter_course, "SessionLocal", session_factory)
    monkeypatch.setattr(sys, "argv", ["seed_starter_course", *args])
    code = seed_starter_course.main()
    return code, capsys.readouterr().out


def test_script_tells_you_to_create_a_super_admin_first(monkeypatch, capsys, session_factory):
    code, out = run_script(monkeypatch, capsys, session_factory)
    assert code == 1 and "create_super_admin" in out


def test_script_adds_everything_then_says_it_is_already_there(monkeypatch, capsys, session_factory, world):
    code, out = run_script(monkeypatch, capsys, session_factory)
    assert code == 0
    assert "Owner: super@x.com" in out and "15 added" in out and "published" in out
    code, out = run_script(monkeypatch, capsys, session_factory)
    assert code == 0 and "0 added, 15 already there" in out and "already exists" in out


def test_script_draft_option_and_unknown_owner(monkeypatch, capsys, client, world, login, session_factory):
    code, out = run_script(monkeypatch, capsys, session_factory, "--email", "nobody@x.com")
    assert code == 1 and "No super admin" in out
    code, out = run_script(monkeypatch, capsys, session_factory, "--email", "SUPER@x.com", "--draft")
    assert code == 0 and "draft" in out
    assert client.get("/api/v1/courses", headers=login(world["student1"])).json() == []
