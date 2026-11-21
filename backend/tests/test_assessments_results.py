import csv
import io

import pytest

from app.main import app
from app.models import Assessment, Role, Submission
from app.services.assessments import compute_sheets
from app.services.finalizer import optional_judge
from tests.assess_helpers import API, broken, correct, create, finished, half, submit
from tests.helpers import create_problem


@pytest.fixture()
def assignment(client, school, clock):
    return create(client, school, clock, kind="assignment", starts=-10, ends=3000)


def results(client, school, a, who="teacher"):
    res = client.get(f"{API}/assessments/{a['id']}/results", headers=school[who])
    assert res.status_code == 200, res.text
    return res.json()


def add_second_student(client, school, make_user, name="Zed Zimmer"):
    zed = make_user("zed@x.com", Role.student, school["world"]["c1"], name=name)
    client.post(f"{API}/batches/{school['batch']['id']}/members", headers=school["teacher"], json={"user_ids": [zed.id]})
    return zed


# ---------------------------------------------------------------- the results table
def test_results_list_every_student_of_the_batch_even_without_answers(client, school, make_user, assignment, fake_judge):
    zed = add_second_student(client, school, make_user)
    fake_judge.respond = half
    finished(client, school["student"], submit(client, school["student"], assignment["id"], school["p1"]["id"]))
    data = results(client, school, assignment)
    assert [r["name"] for r in data["rows"]] == ["student1", "Zed Zimmer"]  # sorted by name; the outsider is not listed
    first, second = data["rows"]
    assert (first["status"], first["auto_marks"], first["final_marks"]) == ("submitted", 5.0, 5.0)
    assert (second["status"], second["auto_marks"]) == ("no_submission", 0.0)
    assert [(p["marks"], p["possible"], p["passed"], p["total"]) for p in first["per_problem"]] == [(5.0, 10.0, 1, 2), (0.0, 20.0, 0, 0)]
    assert data["total_marks"] == 30 and [p["title"] for p in data["problems"]] == ["Add two numbers", "Add again"]
    assert zed.id in [r["user_id"] for r in data["rows"]]


def test_only_the_owner_sees_results(client, school, assignment, login):
    url = f"{API}/assessments/{assignment['id']}/results"
    assert client.get(url, headers=school["student"]).status_code == 403
    assert client.get(url, headers=login(school["world"]["teacher1b"])).status_code == 404
    assert client.get(url, headers=login(school["world"]["teacher2"])).status_code == 404
    assert client.get(url, headers=school["admin"]).status_code == 200


# ---------------------------------------------------------------- changing a mark by hand
def test_override_changes_the_final_mark_but_keeps_the_automatic_one(client, school, assignment, fake_judge):
    fake_judge.respond = half
    finished(client, school["student"], submit(client, school["student"], assignment["id"], school["p1"]["id"]))
    uid = school["student_user"].id
    url = f"{API}/assessments/{assignment['id']}/results/{uid}"
    row = client.put(url, headers=school["teacher"], json={"override_marks": 8.5, "comment": "  Nice logic  "}).json()
    assert (row["auto_marks"], row["override_marks"], row["final_marks"], row["comment"]) == (5.0, 8.5, 8.5, "Nice logic")
    assert results(client, school, assignment)["rows"][0]["final_marks"] == 8.5
    # a later better answer changes the automatic marks, the teacher's number stays
    fake_judge.respond = correct
    finished(client, school["student"], submit(client, school["student"], assignment["id"], school["p1"]["id"]))
    row = results(client, school, assignment)["rows"][0]
    assert (row["auto_marks"], row["final_marks"]) == (10.0, 8.5)


def test_a_comment_alone_keeps_the_automatic_marks(client, school, assignment, fake_judge):
    fake_judge.respond = correct
    finished(client, school["student"], submit(client, school["student"], assignment["id"], school["p1"]["id"]))
    row = client.put(f"{API}/assessments/{assignment['id']}/results/{school['student_user'].id}", headers=school["teacher"], json={"comment": "Well done"}).json()
    assert (row["override_marks"], row["final_marks"], row["comment"]) == (None, 10.0, "Well done")


def test_clearing_the_override_goes_back_to_automatic_marks(client, school, assignment, fake_judge):
    fake_judge.respond = correct
    finished(client, school["student"], submit(client, school["student"], assignment["id"], school["p1"]["id"]))
    url = f"{API}/assessments/{assignment['id']}/results/{school['student_user'].id}"
    client.put(url, headers=school["teacher"], json={"override_marks": 3})
    row = client.put(url, headers=school["teacher"], json={}).json()
    assert (row["override_marks"], row["final_marks"], row["comment"]) == (None, 10.0, None)


def test_override_limits_and_permissions(client, school, assignment, login, make_user):
    uid = school["student_user"].id
    url = f"{API}/assessments/{assignment['id']}/results/{uid}"
    assert client.put(url, headers=school["teacher"], json={"override_marks": 30}).status_code == 200  # exactly the total
    too_high = client.put(url, headers=school["teacher"], json={"override_marks": 30.5})
    assert too_high.status_code == 422 and "more than the total" in too_high.json()["detail"]
    assert client.put(url, headers=school["teacher"], json={"override_marks": -1}).status_code == 422
    assert client.put(url, headers=school["student"], json={"override_marks": 1}).status_code == 403
    assert client.put(url, headers=login(school["world"]["teacher1b"]), json={"override_marks": 1}).status_code == 404
    outsider_url = f"{API}/assessments/{assignment['id']}/results/{school['outsider_user'].id}"
    assert client.put(outsider_url, headers=school["teacher"], json={"override_marks": 1}).status_code == 404  # not in this batch
    assert client.put(f"{API}/assessments/{assignment['id']}/results/9999", headers=school["teacher"], json={}).status_code == 404


# ---------------------------------------------------------------- CSV export
def read_csv(response):
    assert response.status_code == 200, response.text
    return list(csv.reader(io.StringIO(response.text.lstrip("\ufeff"))))


def test_csv_has_one_row_per_student_with_marks(client, school, make_user, assignment, fake_judge):
    add_second_student(client, school, make_user)
    fake_judge.respond = correct
    finished(client, school["student"], submit(client, school["student"], assignment["id"], school["p1"]["id"]))
    client.put(f"{API}/assessments/{assignment['id']}/results/{school['student_user'].id}", headers=school["teacher"], json={"override_marks": 9, "comment": "ok, thanks"})
    res = client.get(f"{API}/assessments/{assignment['id']}/export", headers=school["teacher"])
    assert res.headers["content-type"].startswith("text/csv")
    assert f"assessment-{assignment['id']}-results.csv" in res.headers["content-disposition"]
    assert res.text.startswith("\ufeff")  # so Excel shows names in any language correctly
    rows = read_csv(res)
    assert rows[0] == ["Name", "Email", "Status", "Add two numbers (/10)", "Add again (/20)", "Automatic marks (/30)", "Final marks", "Teacher comment", "Tab switches"]
    assert rows[1] == ["student1", "student1@x.com", "submitted", "10.0", "0.0", "10.0", "9.0", "ok, thanks", "0"]
    assert rows[2][:3] == ["Zed Zimmer", "zed@x.com", "no_submission"]


def test_csv_defuses_spreadsheet_formulas(client, school, make_user, clock):
    evil = create_problem(client, school["teacher"], title="=EVIL()")
    a = create(client, school, clock, kind="assignment", starts=-5, ends=3000, problems=[(evil["id"], 10)])
    add_second_student(client, school, make_user, name='=HYPERLINK("http://bad.example","click")')
    client.put(f"{API}/assessments/{a['id']}/results/{school['student_user'].id}", headers=school["teacher"], json={"comment": "+1+1"})
    rows = read_csv(client.get(f"{API}/assessments/{a['id']}/export", headers=school["teacher"]))
    flat = [cell for row in rows for cell in row]
    assert not any(cell.startswith(("=", "+", "-", "@")) for cell in flat), flat  # nothing can run as a formula
    assert "'=EVIL() (/10)" in flat and "'+1+1" in flat
    assert any(cell.startswith("'=HYPERLINK") for cell in flat)


def test_only_the_owner_exports(client, school, assignment, login):
    url = f"{API}/assessments/{assignment['id']}/export"
    assert client.get(url, headers=school["student"]).status_code == 403
    assert client.get(url, headers=login(school["world"]["teacher1b"])).status_code == 404
    assert client.get(url).status_code == 401


# ---------------------------------------------------------------- when the judge fails
def test_judge_failures_are_counted_and_can_be_judged_again(client, school, assignment, fake_judge):
    fake_judge.respond = broken
    sub = finished(client, school["student"], submit(client, school["student"], assignment["id"], school["p1"]["id"]))
    assert sub["status"] == "error"
    data = results(client, school, assignment)
    row = data["rows"][0]
    assert (row["judge_errors"], row["auto_marks"], data["judge_errors_total"]) == (1, 0.0, 1)  # not silently zero: the teacher is told
    fake_judge.respond = correct
    res = client.post(f"{API}/assessments/{assignment['id']}/rejudge", headers=school["teacher"])
    assert res.status_code == 200 and res.json() == {"requeued": 1}
    row = results(client, school, assignment)["rows"][0]
    assert (row["judge_errors"], row["auto_marks"], row["pending"]) == (0, 10.0, 0)


def test_rejudge_needs_a_judge_and_a_teacher(client, school, assignment):
    url = f"{API}/assessments/{assignment['id']}/rejudge"
    assert client.post(url, headers=school["student"]).status_code == 403
    app.dependency_overrides[optional_judge] = lambda: None  # the judge is not set up
    res = client.post(url, headers=school["teacher"])
    assert res.status_code == 503 and "JUDGE_BACKEND" in res.json()["detail"]


def test_viewing_an_exam_never_fails_just_because_the_judge_is_missing(client, school, clock):
    exam = create(client, school, clock, kind="exam", starts=-5, ends=120, duration=60)
    app.dependency_overrides[optional_judge] = lambda: None
    assert client.post(f"{API}/assessments/{exam['id']}/start", headers=school["student"]).status_code == 200
    assert client.get(f"{API}/assessments/{exam['id']}", headers=school["student"]).status_code == 200
    assert client.get(f"{API}/assessments/{exam['id']}/results", headers=school["teacher"]).status_code == 200


def test_answers_that_were_never_judged_get_another_go_when_results_are_opened(client, school, clock, assignment, fake_judge, db_session):
    stuck = Submission(
        user_id=school["student_user"].id, problem_id=school["p1"]["id"], assessment_id=assignment["id"], kind="submit",
        language="python", source_code="x", status="queued", created_at=clock.at(minutes=-5),
    )
    fresh = Submission(
        user_id=school["student_user"].id, problem_id=school["p2"]["id"], assessment_id=assignment["id"], kind="submit",
        language="python", source_code="y", status="queued", created_at=clock.now,
    )
    db_session.add_all([stuck, fresh])
    db_session.commit()
    fake_judge.respond = correct
    data = results(client, school, assignment)
    db_session.expire_all()
    assert db_session.get(Submission, stuck.id).status == "done"  # old and forgotten: judged now
    assert db_session.get(Submission, fresh.id).status == "queued"  # just sent: probably still being judged, leave it
    assert data["rows"][0]["pending"] == 2 and data["pending_total"] == 2  # counts were taken before the retry finished
    assert results(client, school, assignment)["rows"][0]["pending"] == 1


# ---------------------------------------------------------------- the marks calculation itself
def sheet_for(db_session, a, user):
    db_session.expire_all()
    return compute_sheets(db_session, db_session.get(Assessment, a["id"]), [user.id])[user.id]


def add_sub(db_session, school, a, problem, passed, total, status="done", kind="submit", assessment=True, user=None):
    db_session.add(Submission(
        user_id=(user or school["student_user"]).id, problem_id=problem["id"], assessment_id=a["id"] if assessment else None,
        kind=kind, language="python", source_code="x", status=status, verdict="x", passed_count=passed, total_count=total,
    ))
    db_session.commit()


def test_marks_are_rounded_to_two_decimals(school, assignment, db_session):
    add_sub(db_session, school, assignment, school["p1"], 1, 3)  # 10 x 1/3
    sheet = sheet_for(db_session, assignment, school["student_user"])
    assert sheet.per_problem[0].marks == 3.33 and sheet.auto_marks == 3.33


def test_best_submission_wins_and_each_problem_counts_separately(school, assignment, db_session):
    add_sub(db_session, school, assignment, school["p1"], 1, 4)
    add_sub(db_session, school, assignment, school["p1"], 3, 4)
    add_sub(db_session, school, assignment, school["p1"], 2, 4)
    add_sub(db_session, school, assignment, school["p2"], 4, 4)
    sheet = sheet_for(db_session, assignment, school["student_user"])
    assert [p.marks for p in sheet.per_problem] == [7.5, 20.0] and sheet.auto_marks == 27.5


def test_things_that_must_not_count(school, assignment, client, clock, db_session):
    other = create(client, school, clock, kind="assignment", starts=-5, ends=3000)
    add_sub(db_session, school, assignment, school["p1"], 2, 2, kind="run")  # a Run is only a test
    add_sub(db_session, school, assignment, school["p1"], 2, 2, assessment=False)  # practice outside the assignment
    add_sub(db_session, school, other, school["p1"], 2, 2)  # a different assessment
    add_sub(db_session, school, assignment, school["p1"], 2, 2, status="error")  # the judge failed
    add_sub(db_session, school, assignment, school["p1"], None, None, status="queued")  # not judged yet
    sheet = sheet_for(db_session, assignment, school["student_user"])
    assert sheet.auto_marks == 0.0 and (sheet.pending, sheet.judge_errors) == (1, 1)
    assert sheet.per_problem[0].attempted is True  # the student did try


def test_another_students_answers_are_not_mixed_in(school, assignment, db_session):
    add_sub(db_session, school, assignment, school["p1"], 2, 2, user=school["outsider_user"])
    assert sheet_for(db_session, assignment, school["student_user"]).auto_marks == 0.0
