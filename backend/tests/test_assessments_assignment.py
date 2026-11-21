import pytest

from tests.assess_helpers import API, correct, create, finished, half, submit, wrong

DAYS = 60 * 24


@pytest.fixture()
def open_assignment(client, school, clock):
    """An assignment that is open now and closes in 5 days."""
    return create(client, school, clock, kind="assignment", starts=-10, ends=5 * DAYS)


def detail(client, school, a, who="student"):
    return client.get(f"{API}/assessments/{a['id']}", headers=school[who]).json()


def test_before_it_starts_the_problems_are_hidden_and_answers_are_refused(client, school, clock):
    a = create(client, school, clock, kind="assignment", starts=60, ends=3 * DAYS)
    d = detail(client, school, a)
    assert d["status"] == "upcoming" and d["problems"] is None
    assert client.get(f"{API}/assessments/{a['id']}/problems/{school['p1']['id']}", headers=school["student"]).status_code == 403
    res = submit(client, school["student"], a["id"], school["p1"]["id"])
    assert res.status_code == 403 and "not started" in res.json()["detail"]


def test_when_open_students_see_the_problems_with_samples_only(client, school, clock, open_assignment):
    d = detail(client, school, open_assignment)
    assert d["status"] == "open" and [p["title"] for p in d["problems"]] == ["Add two numbers", "Add again"]
    p = client.get(f"{API}/assessments/{open_assignment['id']}/problems/{school['p1']['id']}", headers=school["student"]).json()
    assert p["title"] == "Add two numbers" and p["can_edit"] is False
    assert [t["is_hidden"] for t in p["test_cases"]] == [False]  # the hidden test never reaches the student


def test_answers_are_judged_and_the_student_sees_the_verdict_at_once(client, school, clock, open_assignment, fake_judge):
    fake_judge.respond = correct
    res = submit(client, school["student"], open_assignment["id"], school["p1"]["id"])
    sub = finished(client, school["student"], res)
    assert sub["verdict"] == "accepted" and sub["hidden"] is False and sub["assessment_id"] == open_assignment["id"]
    assert (sub["passed_count"], sub["total_count"]) == (2, 2)


def test_marks_are_live_and_scaled_by_tests_passed(client, school, clock, open_assignment, fake_judge):
    p1, p2 = school["p1"]["id"], school["p2"]["id"]
    fake_judge.respond = half  # passes 1 of 2 tests
    finished(client, school["student"], submit(client, school["student"], open_assignment["id"], p1))
    d = detail(client, school, open_assignment)
    assert d["my_marks"] == 5.0  # 10 marks x 1/2
    score = {p["problem_id"]: p["score"] for p in d["problems"]}
    assert (score[p1]["marks"], score[p1]["passed"], score[p1]["total"], score[p1]["attempted"]) == (5.0, 1, 2, True)
    assert score[p2]["marks"] == 0 and score[p2]["attempted"] is False
    fake_judge.respond = correct
    finished(client, school["student"], submit(client, school["student"], open_assignment["id"], p2))
    assert detail(client, school, open_assignment)["my_marks"] == 25.0  # 5 + 20


def test_the_best_answer_counts_not_the_last(client, school, clock, open_assignment, fake_judge):
    p1 = school["p1"]["id"]
    fake_judge.respond = correct
    finished(client, school["student"], submit(client, school["student"], open_assignment["id"], p1))
    fake_judge.respond = wrong  # a worse answer later must not lower the marks
    finished(client, school["student"], submit(client, school["student"], open_assignment["id"], p1))
    assert detail(client, school, open_assignment)["my_marks"] == 10.0


def test_answers_for_other_problems_or_without_the_assessment_do_not_count(client, school, clock, open_assignment, fake_judge):
    fake_judge.respond = correct
    outside = {"problem_id": school["p1"]["id"], "language": "python", "source_code": "x"}
    client.post(f"{API}/submissions", headers=school["student"], json=outside)  # normal practice, no assessment
    assert detail(client, school, open_assignment)["my_marks"] == 0


def test_after_the_deadline_nothing_more_is_accepted_but_problems_stay_readable(client, school, clock, open_assignment, fake_judge):
    fake_judge.respond = correct
    finished(client, school["student"], submit(client, school["student"], open_assignment["id"], school["p1"]["id"]))
    clock.advance(days=6)
    res = submit(client, school["student"], open_assignment["id"], school["p1"]["id"])
    assert res.status_code == 403 and "closed" in res.json()["detail"]
    d = detail(client, school, open_assignment)
    assert d["status"] == "closed" and d["problems"] is not None and d["my_marks"] == 10.0


def test_run_works_inside_an_assignment_and_is_refused_when_closed(client, school, clock, open_assignment, fake_judge):
    payload = {"language": "python", "source_code": "x", "stdin": "1 2", "problem_id": school["p1"]["id"], "assessment_id": open_assignment["id"]}
    assert client.post(f"{API}/run", headers=school["student"], json=payload).status_code == 202
    clock.advance(days=6)
    assert client.post(f"{API}/run", headers=school["student"], json=payload).status_code == 403


def test_problem_not_in_the_assignment_is_refused(client, school, clock, open_assignment):
    from tests.helpers import create_problem

    other = create_problem(client, school["teacher"], title="Not included")
    assert submit(client, school["student"], open_assignment["id"], other["id"]).status_code == 404
    assert client.get(f"{API}/assessments/{open_assignment['id']}/problems/{other['id']}", headers=school["student"]).status_code == 404


def test_only_students_of_the_batch_can_submit(client, school, clock, open_assignment):
    assert submit(client, school["outsider"], open_assignment["id"], school["p1"]["id"]).status_code == 404
    assert submit(client, school["teacher"], open_assignment["id"], school["p1"]["id"]).status_code == 403  # teachers do not take assignments


def test_the_teachers_changes_and_comment_show_only_after_results_are_published(client, school, clock, open_assignment, fake_judge):
    fake_judge.respond = half
    finished(client, school["student"], submit(client, school["student"], open_assignment["id"], school["p1"]["id"]))
    uid = school["student_user"].id
    res = client.put(f"{API}/assessments/{open_assignment['id']}/results/{uid}", headers=school["teacher"], json={"override_marks": 9, "comment": "Good effort"})
    assert res.status_code == 200
    mine = client.get(f"{API}/assessments/{open_assignment['id']}/my-result", headers=school["student"]).json()
    assert (mine["visible"], mine["auto_marks"], mine["final_marks"], mine["comment"]) == (True, 5.0, None, None)
    client.patch(f"{API}/assessments/{open_assignment['id']}", headers=school["teacher"], json={"results_published": True})
    mine = client.get(f"{API}/assessments/{open_assignment['id']}/my-result", headers=school["student"]).json()
    assert (mine["auto_marks"], mine["final_marks"], mine["comment"]) == (5.0, 9.0, "Good effort")
    assert detail(client, school, open_assignment)["my_marks"] == 9.0
