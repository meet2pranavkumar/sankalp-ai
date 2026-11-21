from datetime import datetime

import pytest

from tests.assess_helpers import API, body, correct, create, iso, submit
from tests.helpers import create_problem


# ---------------------------------------------------------------- creating
def test_teacher_creates_an_exam_as_a_draft(client, school, clock):
    res = client.post(f"{API}/assessments", headers=school["teacher"], json=body(school, clock))
    assert res.status_code == 201
    a = res.json()
    assert (a["type"], a["is_published"], a["results_published"]) == ("exam", False, False)
    assert a["total_marks"] == 30 and a["problem_count"] == 2 and a["duration_min"] == 60
    assert a["batch_name"] == "CSE Sem 3" and a["can_manage"] is True and a["status"] is None
    assert [(p["title"], p["marks"], p["position"]) for p in a["problems"]] == [("Add two numbers", 10, 1), ("Add again", 20, 2)]
    assert a["has_activity"] is False


def test_assignment_has_no_duration(client, school, clock):
    res = client.post(f"{API}/assessments", headers=school["teacher"], json=body(school, clock, kind="assignment", starts=0, ends=60 * 24 * 5))
    assert res.status_code == 201 and res.json()["duration_min"] is None


@pytest.mark.parametrize(
    "changes,message",
    [
        ({"starts": 60, "ends": 30}, "end time must be after"),
        ({"starts": -120, "ends": -60}, "must be in the future"),
        ({"duration": 90, "ends": 60}, "longer than the time window"),
        ({"problems": []}, None),
        ({"problems": [(1, 0)]}, None),
        ({"duration": 2}, None),
    ],
)
def test_bad_schedules_and_problem_lists_are_rejected(client, school, clock, changes, message):
    res = client.post(f"{API}/assessments", headers=school["teacher"], json=body(school, clock, **changes))
    assert res.status_code == 422
    if message:
        assert message in res.json()["detail"]


def test_exam_needs_a_duration_and_assignment_must_not_have_one(client, school, clock):
    no_duration = body(school, clock)
    del no_duration["duration_min"]
    res = client.post(f"{API}/assessments", headers=school["teacher"], json=no_duration)
    assert res.status_code == 422 and "needs a duration" in res.json()["detail"]
    res = client.post(f"{API}/assessments", headers=school["teacher"], json=body(school, clock, kind="assignment", duration_min=30))
    assert res.status_code == 422 and "no duration" in res.json()["detail"]


def test_times_must_carry_a_time_zone(client, school, clock):
    data = body(school, clock)
    data["starts_at"] = clock.at(minutes=-5).replace(tzinfo=None).isoformat()
    assert client.post(f"{API}/assessments", headers=school["teacher"], json=data).status_code == 422


def test_a_problem_can_only_be_used_once(client, school, clock):
    p = school["p1"]["id"]
    assert client.post(f"{API}/assessments", headers=school["teacher"], json=body(school, clock, problems=[(p, 5), (p, 5)])).status_code == 422


# ---------------------------------------------------------------- who may create
def test_students_cannot_create_assessments(client, school, clock):
    assert client.post(f"{API}/assessments", headers=school["student"], json=body(school, clock)).status_code == 403


def test_a_teacher_can_only_use_their_own_batches(client, school, clock, login):
    other_teacher = login(school["world"]["teacher1b"])
    assert client.post(f"{API}/assessments", headers=other_teacher, json=body(school, clock)).status_code == 404
    assert client.post(f"{API}/assessments", headers=login(school["world"]["teacher2"]), json=body(school, clock)).status_code == 404


def test_an_admin_can_use_any_batch_of_their_college(client, school, clock):
    assert client.post(f"{API}/assessments", headers=school["admin"], json=body(school, clock)).status_code == 201


def test_super_admin_cannot_create_assessments(client, school, clock, login):
    assert client.post(f"{API}/assessments", headers=login(school["world"]["super"]), json=body(school, clock)).status_code == 403


def test_problems_from_other_colleges_cannot_be_used_but_shared_ones_can(client, school, clock, login):
    foreign = create_problem(client, login(school["world"]["teacher2"]), title="Foreign")
    res = client.post(f"{API}/assessments", headers=school["teacher"], json=body(school, clock, problems=[(foreign["id"], 5)]))
    assert res.status_code == 404
    shared = create_problem(client, login(school["world"]["super"]), title="Shared")
    res = client.post(f"{API}/assessments", headers=school["teacher"], json=body(school, clock, problems=[(shared["id"], 5)]))
    assert res.status_code == 201


# ---------------------------------------------------------------- who sees it
def test_a_draft_is_invisible_to_students(client, school, clock):
    a = create(client, school, clock, publish=False)
    assert client.get(f"{API}/assessments", headers=school["student"]).json() == []
    assert client.get(f"{API}/assessments/{a['id']}", headers=school["student"]).status_code == 404
    assert [x["id"] for x in client.get(f"{API}/assessments", headers=school["teacher"]).json()] == [a["id"]]


def test_published_assessment_is_seen_only_by_the_batch(client, school, clock, login):
    a = create(client, school, clock)
    listed = client.get(f"{API}/assessments", headers=school["student"]).json()
    assert [(x["id"], x["status"], x["can_manage"], x["my_marks"]) for x in listed] == [(a["id"], "ready", False, None)]
    url = f"{API}/assessments/{a['id']}"
    assert client.get(url, headers=school["outsider"]).status_code == 404  # same college, other batch
    assert client.get(f"{API}/assessments", headers=school["outsider"]).json() == []
    assert client.get(url, headers=login(school["world"]["student2"])).status_code == 404  # other college


def test_teachers_see_only_what_they_manage(client, school, clock, login):
    a = create(client, school, clock)
    assert [x["id"] for x in client.get(f"{API}/assessments", headers=school["admin"]).json()] == [a["id"]]
    assert client.get(f"{API}/assessments", headers=login(school["world"]["teacher1b"])).json() == []
    assert client.get(f"{API}/assessments/{a['id']}", headers=login(school["world"]["teacher1b"])).status_code == 404
    assert client.get(f"{API}/assessments/{a['id']}", headers=login(school["world"]["teacher2"])).status_code == 404


def test_assessments_need_login(client):
    assert client.get(f"{API}/assessments").status_code == 401


# ---------------------------------------------------------------- changing and deleting
def test_teacher_can_change_details_before_anyone_starts(client, school, clock):
    a = create(client, school, clock, publish=False)
    url = f"{API}/assessments/{a['id']}"
    res = client.patch(url, headers=school["teacher"], json={"title": "Final", "description": "Bring a pen", "problems": [{"problem_id": school["p2"]["id"], "marks": 50}]})
    assert res.status_code == 200
    assert (res.json()["title"], res.json()["total_marks"], res.json()["problem_count"]) == ("Final", 50, 1)


def test_times_are_rechecked_when_changed(client, school, clock):
    a = create(client, school, clock)
    url = f"{API}/assessments/{a['id']}"
    assert client.patch(url, headers=school["teacher"], json={"ends_at": iso(clock.at(minutes=-30))}).status_code == 422
    assert client.patch(url, headers=school["teacher"], json={"duration_min": 500}).status_code == 422  # longer than the window
    ok = client.patch(url, headers=school["teacher"], json={"ends_at": iso(clock.at(minutes=300)), "duration_min": 120})
    assert ok.status_code == 200 and ok.json()["duration_min"] == 120


def test_once_students_have_started_problems_are_frozen(client, school, clock):
    a = create(client, school, clock)
    client.post(f"{API}/assessments/{a['id']}/start", headers=school["student"])
    url = f"{API}/assessments/{a['id']}"
    assert client.get(url, headers=school["teacher"]).json()["has_activity"] is True
    changed = client.patch(url, headers=school["teacher"], json={"problems": [{"problem_id": school["p1"]["id"], "marks": 99}]})
    assert changed.status_code == 409
    assert client.patch(url, headers=school["teacher"], json={"is_published": False}).status_code == 409
    assert client.patch(url, headers=school["teacher"], json={"title": "Renamed"}).status_code == 200  # harmless changes are fine
    assert client.delete(url, headers=school["teacher"]).status_code == 409


def test_unused_assessment_can_be_deleted(client, school, clock):
    a = create(client, school, clock)
    assert client.delete(f"{API}/assessments/{a['id']}", headers=school["student"]).status_code == 403
    assert client.delete(f"{API}/assessments/{a['id']}", headers=school["teacher"]).status_code == 204
    assert client.get(f"{API}/assessments/{a['id']}", headers=school["teacher"]).status_code == 404


def test_only_the_owner_can_change_an_assessment(client, school, clock, login):
    a = create(client, school, clock)
    url = f"{API}/assessments/{a['id']}"
    for key in ("teacher1b", "teacher2"):
        assert client.patch(url, headers=login(school["world"][key]), json={"title": "X"}).status_code == 404
    assert client.patch(url, headers=school["student"], json={"title": "X"}).status_code == 403
    assert client.patch(url, headers=school["admin"], json={"title": "By admin"}).status_code == 200
