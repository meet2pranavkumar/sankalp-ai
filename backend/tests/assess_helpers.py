from datetime import timedelta

from app.services.judge.base import JudgeOutcome, RunStatus

API = "/api/v1"


def iso(moment):
    return moment.isoformat()


def correct(job):
    """A pretend student who solves 'print a + b' perfectly."""
    a, b = map(int, job.stdin.split())
    return JudgeOutcome(status=RunStatus.ok, stdout=f"{a + b}\n", time_ms=5, memory_kb=900)


def half(job):
    """Solves the sample test (1 2) but fails the hidden one."""
    if job.stdin.strip() == "1 2":
        return correct(job)
    return JudgeOutcome(status=RunStatus.ok, stdout="0\n", time_ms=5)


def wrong(job):
    return JudgeOutcome(status=RunStatus.ok, stdout="999\n", time_ms=5)


def broken(job):
    return JudgeOutcome(status=RunStatus.internal_error, message="The code judge is down.")


def body(school, clock, kind="exam", starts=-5, ends=120, duration=60, problems=None, **extra):
    """Minutes are relative to now. problems = [(problem_id, marks), ...]"""
    problems = problems if problems is not None else [(school["p1"]["id"], 10), (school["p2"]["id"], 20)]
    data = {
        "batch_id": school["batch"]["id"], "title": "Midterm", "type": kind,
        "starts_at": iso(clock.at(minutes=starts)), "ends_at": iso(clock.at(minutes=ends)),
        "problems": [{"problem_id": pid, "marks": marks} for pid, marks in problems],
    }
    if kind == "exam":
        data["duration_min"] = duration
    data.update(extra)
    return data


def create(client, school, clock, publish=True, **kwargs):
    res = client.post(f"{API}/assessments", headers=school["teacher"], json=body(school, clock, **kwargs))
    assert res.status_code == 201, res.text
    a = res.json()
    if publish:
        res = client.patch(f"{API}/assessments/{a['id']}", headers=school["teacher"], json={"is_published": True})
        assert res.status_code == 200, res.text
        a = res.json()
    return a


def submit(client, headers, assessment_id, problem_id, code="print(1)", language="python"):
    return client.post(
        f"{API}/submissions", headers=headers,
        json={"problem_id": problem_id, "language": language, "source_code": code, "assessment_id": assessment_id},
    )


def finished(client, headers, submission_response):
    """The fake judge is instant, so the answer is ready when we ask."""
    assert submission_response.status_code == 202, submission_response.text
    return client.get(f"{API}/submissions/{submission_response.json()['id']}", headers=headers).json()
