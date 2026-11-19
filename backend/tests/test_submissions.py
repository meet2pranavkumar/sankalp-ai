from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import get_settings
from app.models import Submission
from app.services.judge.base import JudgeOutcome, RunStatus
from tests.helpers import create_problem

CODE = "print(sum(map(int, input().split())))"


@pytest.fixture()
def problem(client, world, login):
    return create_problem(client, login(world["teacher1"]))


def submit(client, headers, problem_id, code=CODE, language="python"):
    return client.post(
        "/api/v1/submissions", headers=headers,
        json={"problem_id": problem_id, "language": language, "source_code": code},
    )


def judged(client, headers, problem_id, **kwargs):
    """Submit and return the finished submission (the fake judge answers instantly)."""
    res = submit(client, headers, problem_id, **kwargs)
    assert res.status_code == 202, res.text
    return client.get(f"/api/v1/submissions/{res.json()['id']}", headers=headers).json()


def answers_correctly(job):
    a, b = map(int, job.stdin.split())
    return JudgeOutcome(status=RunStatus.ok, stdout=f"{a + b}\n", time_ms=7, memory_kb=900)


# ---------- submit ----------
def test_correct_solution_is_accepted(client, world, login, problem, fake_judge):
    fake_judge.respond = answers_correctly
    headers = login(world["student1"])
    res = submit(client, headers, problem["id"])
    assert res.status_code == 202
    # the fake judge is instant, so by the time we ask, it is finished
    done = client.get(f"/api/v1/submissions/{res.json()['id']}", headers=headers).json()
    assert (done["status"], done["verdict"]) == ("done", "accepted")
    assert (done["passed_count"], done["total_count"]) == (2, 2)
    assert done["runtime_ms"] == 7 and done["finished_at"]
    assert len(fake_judge.jobs) == 2  # one job per test case
    assert [j.stdin for j in fake_judge.jobs] == ["1 2\n", "10 20\n"]
    assert fake_judge.jobs[0].time_limit_ms == 1000 and fake_judge.jobs[0].memory_limit_mb == 128


def test_wrong_answer_shows_samples_but_hides_hidden_tests(client, world, login, problem, fake_judge):
    fake_judge.respond = lambda job: JudgeOutcome(status=RunStatus.ok, stdout="999\n")
    headers = login(world["student1"])
    sub = judged(client, headers, problem['id'])
    assert sub["verdict"] == "wrong_answer" and sub["passed_count"] == 0
    sample, hidden = sub["results"]
    assert sample["expected"] == "3\n" and sample["actual"] == "999\n"
    assert "expected" not in hidden and "input" not in hidden
    assert "30" not in str(hidden)


def test_compile_error_is_shown(client, world, login, problem, fake_judge):
    fake_judge.respond = lambda job: JudgeOutcome(status=RunStatus.compile_error, compile_output="error: expected ';'")
    headers = login(world["student1"])
    sub = judged(client, headers, problem['id'], code='int main(')
    assert sub["verdict"] == "compile_error" and "expected ';'" in sub["compile_output"]


def test_judge_failure_is_marked_as_error_not_as_the_students_fault(client, world, login, problem, fake_judge):
    fake_judge.respond = lambda job: JudgeOutcome(status=RunStatus.internal_error, message="The code judge is busy.")
    headers = login(world["student1"])
    sub = judged(client, headers, problem['id'])
    assert sub["status"] == "error" and sub["verdict"] == "internal_error" and "busy" in sub["message"]


def test_a_crashing_judge_does_not_leave_the_submission_stuck(client, world, login, problem, fake_judge):
    def explode(job):
        raise RuntimeError("boom")

    fake_judge.respond = explode
    headers = login(world["student1"])
    sub = judged(client, headers, problem['id'])
    assert sub["status"] == "error" and "try again" in sub["message"].lower()


def test_cannot_submit_to_a_problem_you_cannot_see(client, world, login, problem):
    assert submit(client, login(world["student2"]), problem["id"]).status_code == 404
    assert submit(client, login(world["student1"]), 9999).status_code == 404


def test_bad_language_and_empty_or_huge_code_are_rejected(client, world, login, problem):
    h = login(world["student1"])
    assert submit(client, h, problem["id"], language="cobol").status_code == 422
    assert submit(client, h, problem["id"], code="").status_code == 422
    assert submit(client, h, problem["id"], code="x" * (get_settings().max_source_bytes + 1)).status_code == 422


def test_solved_flag_appears_after_an_accepted_submit(client, world, login, problem, fake_judge):
    headers = login(world["student1"])
    assert client.get("/api/v1/problems", headers=headers).json()[0]["solved"] is False
    fake_judge.respond = lambda job: JudgeOutcome(status=RunStatus.ok, stdout="wrong\n")
    submit(client, headers, problem["id"])
    assert client.get("/api/v1/problems", headers=headers).json()[0]["solved"] is False
    fake_judge.respond = answers_correctly
    submit(client, headers, problem["id"])
    assert client.get("/api/v1/problems", headers=headers).json()[0]["solved"] is True
    # another student's list is not affected
    other = client.get("/api/v1/problems", headers=login(world["teacher1"])).json()[0]
    assert other["solved"] is False


def test_my_submissions_list_is_mine_only_and_newest_first(client, world, login, problem, fake_judge):
    fake_judge.respond = answers_correctly
    mine = login(world["student1"])
    first = submit(client, mine, problem["id"]).json()["id"]
    second = submit(client, mine, problem["id"]).json()["id"]
    submit(client, login(world["teacher1"]), problem["id"])
    listed = client.get(f"/api/v1/problems/{problem['id']}/submissions", headers=mine).json()
    assert [s["id"] for s in listed] == [second, first]
    assert "source_code" not in listed[0]


# ---------- run ----------
def test_run_returns_the_programs_output(client, world, login, fake_judge):
    fake_judge.respond = lambda job: JudgeOutcome(status=RunStatus.ok, stdout=f"you sent: {job.stdin}", time_ms=3)
    headers = login(world["student1"])
    res = client.post("/api/v1/run", headers=headers, json={"language": "python", "source_code": "x", "stdin": "hello"})
    assert res.status_code == 202
    done = client.get(f"/api/v1/submissions/{res.json()['id']}", headers=headers).json()
    assert done["kind"] == "run" and done["verdict"] == "ok" and done["stdout"] == "you sent: hello"
    assert done["problem_id"] is None and done["results"] is None
    assert fake_judge.jobs[0].time_limit_ms == 2000  # default limits when no problem is given


def test_run_with_a_problem_uses_its_limits_and_is_not_counted_as_a_submit(client, world, login, problem, fake_judge):
    headers = login(world["student1"])
    client.post("/api/v1/run", headers=headers, json={"language": "c", "source_code": "x", "problem_id": problem["id"]})
    assert fake_judge.jobs[0].memory_limit_mb == 128
    assert client.get(f"/api/v1/problems/{problem['id']}/submissions", headers=headers).json() == []
    assert client.get("/api/v1/problems", headers=headers).json()[0]["solved"] is False


def test_run_shows_runtime_errors(client, world, login, fake_judge):
    fake_judge.respond = lambda job: JudgeOutcome(status=RunStatus.runtime_error, stderr="ZeroDivisionError", message="NZEC")
    headers = login(world["student1"])
    sid = client.post("/api/v1/run", headers=headers, json={"language": "python", "source_code": "1/0"}).json()["id"]
    done = client.get(f"/api/v1/submissions/{sid}", headers=headers).json()
    assert done["verdict"] == "runtime_error" and "ZeroDivisionError" in done["stderr"]


def test_run_cannot_use_a_problem_from_another_college(client, world, login, problem):
    res = client.post("/api/v1/run", headers=login(world["student2"]), json={"language": "c", "source_code": "x", "problem_id": problem["id"]})
    assert res.status_code == 404


# ---------- who may read a submission ----------
def test_who_can_read_a_submission(client, world, login, problem, fake_judge):
    fake_judge.respond = answers_correctly
    sid = submit(client, login(world["student1"]), problem["id"]).json()["id"]
    url = f"/api/v1/submissions/{sid}"
    for key in ("student1", "teacher1", "teacher1b", "admin1", "super"):
        assert client.get(url, headers=login(world[key])).status_code == 200, key
    for key in ("student2", "teacher2", "admin2"):
        assert client.get(url, headers=login(world[key])).status_code == 404, key
    assert client.get(url).status_code == 401
    assert client.get("/api/v1/submissions/9999", headers=login(world["student1"])).status_code == 404


def test_other_students_in_the_same_college_cannot_read_my_code(client, world, login, problem, make_user, fake_judge):
    from app.models import Role

    fake_judge.respond = answers_correctly
    sid = submit(client, login(world["student1"]), problem["id"]).json()["id"]
    classmate = make_user("classmate@x.com", Role.student, world["c1"])
    assert client.get(f"/api/v1/submissions/{sid}", headers=login(classmate)).status_code == 404


# ---------- limits and failures ----------
def test_cooldown_stops_rapid_fire_submits(client, world, login, problem, fake_judge, monkeypatch):
    monkeypatch.setattr(get_settings(), "submit_cooldown_seconds", 30)
    headers = login(world["student1"])
    assert submit(client, headers, problem["id"]).status_code == 202
    res = submit(client, headers, problem["id"])
    assert res.status_code == 429 and "wait" in res.json()["detail"].lower()
    assert int(res.headers["retry-after"]) >= 1
    # another student is not affected, and Run has its own timer
    assert submit(client, login(world["teacher1"]), problem["id"]).status_code == 202
    assert client.post("/api/v1/run", headers=headers, json={"language": "c", "source_code": "x"}).status_code == 202


def test_stuck_submission_is_released_after_a_long_wait(client, world, login, problem, db_session):
    headers = login(world["student1"])
    old = Submission(
        user_id=world["student1"].id, problem_id=problem["id"], kind="submit", language="c",
        source_code="x", status="running", created_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    db_session.add(old)
    db_session.commit()
    sub = client.get(f"/api/v1/submissions/{old.id}", headers=headers).json()
    assert sub["status"] == "error" and "interrupted" in sub["message"]


def test_a_fresh_queued_submission_is_left_alone(client, world, login, problem, db_session):
    fresh = Submission(user_id=world["student1"].id, problem_id=problem["id"], kind="submit", language="c", source_code="x", status="queued")
    db_session.add(fresh)
    db_session.commit()
    assert client.get(f"/api/v1/submissions/{fresh.id}", headers=login(world["student1"])).json()["status"] == "queued"


def test_missing_judge_setup_gives_a_clear_503(client, world, login, problem, monkeypatch):
    from app.main import app
    from app.routers import submissions as module

    app.dependency_overrides.pop(module.judge_dependency)

    def broken():
        raise RuntimeError("Unknown JUDGE_BACKEND 'nope'.")

    monkeypatch.setattr(module, "get_judge", broken)
    res = submit(client, login(world["student1"]), problem["id"])
    assert res.status_code == 503 and "JUDGE_BACKEND" in res.json()["detail"]
