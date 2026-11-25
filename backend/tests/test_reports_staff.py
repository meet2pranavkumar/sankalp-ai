import csv
import io
from datetime import timedelta

import pytest

from app.models import AssessmentAttempt, Role
from tests.assess_helpers import create
from tests.helpers import create_problem
from tests.report_helpers import API, add_sub, ai_request, at, course_with_lessons, lesson_done


def add_student(client, school, make_user, email, name):
    user = make_user(email, Role.student, school["world"]["c1"], name=name)
    client.post(f"{API}/batches/{school['batch']['id']}/members", headers=school["teacher"], json={"user_ids": [user.id]})
    return user


@pytest.fixture()
def team(client, school, day, make_user):
    """student1 (in the school fixture) plus zed and amy, all in teacher1's batch."""
    return {"s1": school["student_user"], "zed": add_student(client, school, make_user, "zed@x.com", "Zed Zimmer"),
            "amy": add_student(client, school, make_user, "amy@x.com", "amy adams")}


def report(client, school, who="teacher", days=7, batch=None):
    res = client.get(f"{API}/reports/batches/{(batch or school['batch'])['id']}", headers=school[who], params={"inactive_days": days})
    assert res.status_code == 200, res.text
    return res.json()


def rows_by_name(r):
    return {x["name"]: x for x in r["students"]}


# ---------------------------------------------------------------- who sees which batches
def test_batch_list_follows_the_teachers_and_the_colleges(client, school, day, login):
    other = login(school["world"]["teacher1b"])
    mine_b = client.post(f"{API}/batches", headers=other, json={"name": "Other teacher batch", "year": 2026}).json()
    listed = lambda h: [b["name"] for b in client.get(f"{API}/reports/batches", headers=h).json()]
    assert listed(school["teacher"]) == ["CSE Sem 3"]
    assert listed(other) == ["Other teacher batch"]
    assert sorted(listed(school["admin"])) == ["CSE Sem 3", "Other teacher batch"]
    assert listed(login(school["world"]["teacher2"])) == [] and listed(login(school["world"]["admin2"])) == []
    assert client.get(f"{API}/reports/batches", headers=school["student"]).status_code == 403
    assert client.get(f"{API}/reports/batches", headers=login(school["world"]["super"])).status_code == 403
    assert client.get(f"{API}/reports/batches").status_code == 401
    assert mine_b["id"] != school["batch"]["id"]


def test_one_batch_report_is_for_its_teacher_and_the_college_admin_only(client, school, day, login):
    url = f"{API}/reports/batches/{school['batch']['id']}"
    assert client.get(url, headers=school["teacher"]).status_code == 200
    assert client.get(url, headers=school["admin"]).status_code == 200
    for who in ("teacher1b", "teacher2", "admin2"):
        assert client.get(url, headers=login(school["world"][who])).status_code == 404, who
        assert client.get(url + "/export", headers=login(school["world"][who])).status_code == 404, who
    assert client.get(url, headers=school["student"]).status_code == 403
    assert client.get(f"{API}/reports/batches/9999", headers=school["teacher"]).status_code == 404


def test_the_inactive_days_setting_is_checked(client, school, day):
    url = f"{API}/reports/batches/{school['batch']['id']}"
    for bad in (0, 400):
        assert client.get(url, headers=school["teacher"], params={"inactive_days": bad}).status_code == 422


# ---------------------------------------------------------------- the student table
def test_every_student_of_the_batch_gets_a_row_sorted_by_name_without_regard_to_capitals(client, school, team, day):
    r = report(client, school)
    assert [x["name"] for x in r["students"]] == ["amy adams", "student1", "Zed Zimmer"]
    assert school["outsider_user"].id not in [x["user_id"] for x in r["students"]]  # a classmate in no batch is not listed


def test_rows_show_progress_and_last_activity(client, school, team, day, db_session):
    _, lessons = course_with_lessons(client, school["teacher"], count=4)
    p1, p2 = school["p1"]["id"], school["p2"]["id"]
    for lid in lessons[:2]:
        lesson_done(db_session, team["s1"], lid, at(0))
    for lid in lessons:
        lesson_done(db_session, team["zed"], lid, at(12))
    add_sub(db_session, team["s1"], p1, "accepted", when=at(0))
    add_sub(db_session, team["zed"], p1, "accepted", when=at(12))
    add_sub(db_session, team["zed"], p2, "accepted", when=at(12))
    add_sub(db_session, team["zed"], p2, "accepted", when=at(12))  # the same problem twice is one problem
    add_sub(db_session, team["zed"], p1, "wrong_answer", when=at(40))  # older than 30 days: not in the 30 day count
    rows = rows_by_name(report(client, school))
    s1, zed, amy = rows["student1"], rows["Zed Zimmer"], rows["amy adams"]
    assert (s1["lessons_completed"], s1["lessons_total"], s1["completion_percent"], s1["problems_solved"]) == (2, 4, 50.0, 1)
    assert (zed["completion_percent"], zed["problems_solved"], zed["submissions_30d"]) == (100.0, 2, 3)
    assert (amy["lessons_completed"], amy["completion_percent"], amy["last_active_at"], amy["days_inactive"]) == (0, 0.0, None, None)
    assert (s1["days_inactive"], zed["days_inactive"]) == (0, 12)


def test_inactive_means_no_activity_for_that_many_days(client, school, team, day, db_session):
    add_sub(db_session, team["s1"], school["p1"]["id"], "wrong_answer", when=at(0))
    add_sub(db_session, team["zed"], school["p1"]["id"], "wrong_answer", when=at(10))
    status = lambda days: {n: x["status"] for n, x in rows_by_name(report(client, school, days=days)).items()}
    assert status(7) == {"student1": "active", "Zed Zimmer": "inactive", "amy adams": "never_active"}
    assert status(14) == {"student1": "active", "Zed Zimmer": "active", "amy adams": "never_active"}
    assert status(10)["Zed Zimmer"] == "inactive"  # exactly 10 days without activity counts
    assert status(11)["Zed Zimmer"] == "active"


def test_any_kind_of_activity_makes_a_student_active(client, school, team, day, db_session):
    _, lessons = course_with_lessons(client, school["teacher"])
    add_sub(db_session, team["s1"], school["p1"]["id"], "ok", kind="run", when=at(1))  # only ran some code
    lesson_done(db_session, team["zed"], lessons[0], at(1))  # only read a lesson
    exam = create(client, school, day, kind="exam", starts=-5, ends=120, duration=60)
    db_session.add(AssessmentAttempt(assessment_id=exam["id"], user_id=team["amy"].id, started_at=at(1), deadline_at=at(1) + timedelta(hours=1)))
    db_session.commit()
    assert {x["status"] for x in report(client, school)["students"]} == {"active"}


def test_ai_helper_use_is_counted_but_failed_requests_and_old_ones_are_not(client, school, team, day, db_session):
    s1, p1 = team["s1"], school["p1"]["id"]
    ai_request(db_session, s1, p1, when=at(1))
    ai_request(db_session, s1, p1, kind="explain", when=at(2))
    ai_request(db_session, s1, p1, status="error", when=at(1))  # the AI service failed: it does not count
    ai_request(db_session, s1, p1, when=at(45))  # too old
    assert rows_by_name(report(client, school))["student1"]["ai_requests_30d"] == 2


def test_deactivated_accounts_are_not_listed(client, school, team, day, db_session):
    team["zed"].is_active = False
    db_session.commit()
    assert "Zed Zimmer" not in rows_by_name(report(client, school))


def test_an_empty_batch_has_a_report_with_zeros(client, school, day, login):
    empty = client.post(f"{API}/batches", headers=school["teacher"], json={"name": "Empty"}).json()
    r = report(client, school, batch=empty)
    assert r["students"] == [] and r["weak_topics"] == [] and r["weak_problems"] == [] and r["assessments"] == []
    assert (r["summary"]["student_count"], r["summary"]["avg_completion_percent"], r["summary"]["last_active_at"]) == (0, 0.0, None)


# ---------------------------------------------------------------- the class summary
def test_summary_averages_and_inactive_count(client, school, team, day, db_session):
    _, lessons = course_with_lessons(client, school["teacher"], count=4)
    for lid in lessons[:2]:
        lesson_done(db_session, team["s1"], lid, at(0))
    for lid in lessons:
        lesson_done(db_session, team["zed"], lid, at(10))
    add_sub(db_session, team["s1"], school["p1"]["id"], "accepted", when=at(0))
    for p in (school["p1"], school["p2"]):
        add_sub(db_session, team["zed"], p["id"], "accepted", when=at(10))
    s = report(client, school)["summary"]
    assert (s["student_count"], s["total_lessons"], s["avg_completion_percent"], s["avg_problems_solved"]) == (3, 4, 50.0, 1.0)  # (50+100+0)/3, (1+2+0)/3
    assert s["inactive_count"] == 2  # Zed (10 days) and amy (never)
    assert s["last_active_at"].startswith("2026-12-10")
    assert report(client, school, days=14)["summary"]["inactive_count"] == 1
    listed = client.get(f"{API}/reports/batches", headers=school["teacher"], params={"inactive_days": 14}).json()[0]
    assert (listed["avg_completion_percent"], listed["inactive_count"], listed["student_count"]) == (50.0, 1, 3)


def test_course_averages(client, school, team, day, db_session):
    _, a = course_with_lessons(client, school["teacher"], count=4, title="A course")
    _, b = course_with_lessons(client, school["teacher"], count=2, title="B course")
    lesson_done(db_session, team["s1"], a[0], at(0))
    for lid in a:
        lesson_done(db_session, team["zed"], lid, at(0))
    lesson_done(db_session, team["s1"], b[0], at(0))
    avgs = {c["title"]: c["avg_percent"] for c in report(client, school)["courses"]}
    assert avgs == {"A course": round((25 + 100 + 0) / 3, 1), "B course": round((50 + 0 + 0) / 3, 1)}


# ---------------------------------------------------------------- where students struggle
def make_problems(client, school):
    teacher = school["teacher"]
    a = create_problem(client, teacher, title="Problem A", tags=["arrays"])
    b = create_problem(client, teacher, title="Problem B", tags=["arrays", "loops"])
    c = create_problem(client, teacher, title="Problem C", tags=["loops"])
    d = create_problem(client, teacher, title="Problem D", tags=["rare"])
    return a, b, c, d


def test_weak_problems_are_the_ones_students_tried_but_did_not_solve(client, school, team, day, db_session, make_user):
    a, b, c, d = make_problems(client, school)
    for who, verdict in (("s1", "wrong_answer"), ("zed", "runtime_error"), ("amy", "accepted")):
        add_sub(db_session, team[who], a["id"], verdict, when=at(3))
    for who in ("s1", "zed", "amy"):
        add_sub(db_session, team[who], b["id"], "accepted", when=at(3))  # everyone solved it: not weak
    add_sub(db_session, team["s1"], c["id"], "wrong_answer", when=at(3))  # only one student tried: not a pattern
    add_sub(db_session, school["outsider_user"], a["id"], "wrong_answer", when=at(3))  # not in the batch
    # Two more students whose ONLY answer on A says nothing about them: the judge failed, or it has not finished yet.
    bob = add_student(client, school, make_user, "bob@x.com", "Bob Judge-failed")
    carl = add_student(client, school, make_user, "carl@x.com", "Carl Still-queued")
    add_sub(db_session, bob, a["id"], "internal_error", when=at(2), status="error")
    add_sub(db_session, carl, a["id"], None, when=at(2), status="queued")
    add_sub(db_session, team["zed"], a["id"], "wrong_answer", when=at(100))  # older than 90 days
    ai_request(db_session, team["s1"], a["id"], when=at(3))
    ai_request(db_session, team["zed"], a["id"], when=at(3))
    ai_request(db_session, team["zed"], a["id"], kind="explain", when=at(3))  # explaining an error is not a hint
    ai_request(db_session, team["zed"], a["id"], status="error", when=at(3))
    weak = report(client, school)["weak_problems"]
    assert [(w["title"], w["students_attempted"], w["students_solved"], w["solve_rate_percent"], w["wrong_submissions"], w["hint_requests"]) for w in weak] == [
        ("Problem A", 3, 1, 33.3, 2, 2)
    ]


def test_weak_topics_group_problems_by_tag(client, school, team, day, db_session):
    a, b, c, d = make_problems(client, school)
    for who, verdict in (("s1", "wrong_answer"), ("zed", "wrong_answer"), ("amy", "accepted")):
        add_sub(db_session, team[who], a["id"], verdict, when=at(3))
    for who in ("s1", "zed", "amy"):
        add_sub(db_session, team[who], b["id"], "accepted", when=at(3))
    add_sub(db_session, team["s1"], c["id"], "wrong_answer", when=at(3))
    for who in ("s1", "zed"):
        add_sub(db_session, team[who], d["id"], "wrong_answer", when=at(3))  # only 2 attempts in "rare": too few to call a pattern
    ai_request(db_session, team["s1"], a["id"], when=at(3))
    topics = {t["topic"]: t for t in report(client, school)["weak_topics"]}
    assert set(topics) == {"arrays", "loops"}
    arrays, loops = topics["arrays"], topics["loops"]
    assert (arrays["students"], arrays["pairs_attempted"], arrays["pairs_solved"], arrays["solve_rate_percent"]) == (3, 6, 4, 66.7)
    assert (arrays["wrong_submissions"], arrays["hint_requests"]) == (2, 1)
    assert (loops["pairs_attempted"], loops["pairs_solved"], loops["solve_rate_percent"]) == (4, 3, 75.0)  # B (3 of 3) and C (0 of 1)
    ordered = [t["topic"] for t in report(client, school)["weak_topics"]]
    assert ordered == ["arrays", "loops"]  # the weakest topic first


def test_a_topic_everyone_solves_is_not_weak(client, school, team, day, db_session):
    a, *_ = make_problems(client, school)
    for who in ("s1", "zed", "amy"):
        add_sub(db_session, team[who], a["id"], "accepted", when=at(3))
    r = report(client, school)
    assert r["weak_problems"] == [] and r["weak_topics"] == []


# ---------------------------------------------------------------- assessments
def test_assessment_averages_use_each_students_final_marks(client, school, team, day, db_session):
    a = create(client, school, day, kind="assignment", starts=-10, ends=3000)  # p1: 10 marks, p2: 20 marks, 30 in total
    p1, p2 = school["p1"]["id"], school["p2"]["id"]
    for p in (p1, p2):
        add_sub(db_session, team["s1"], p, "accepted", assessment_id=a["id"], when=at(0))
    add_sub(db_session, team["zed"], p1, "accepted", assessment_id=a["id"], when=at(0))  # 10 of 30
    row = report(client, school)["assessments"][0]
    assert (row["title"], row["type"], row["students"], row["participants"], row["avg_percent"]) == ("Midterm", "assignment", 3, 2, round((100 + 33.3) / 2, 1))
    client.put(f"{API}/assessments/{a['id']}/results/{team['zed'].id}", headers=school["teacher"], json={"override_marks": 20})
    assert report(client, school)["assessments"][0]["avg_percent"] == round((100 + 66.7) / 2, 1)  # the teacher's mark counts


def test_starting_an_exam_counts_as_taking_part_and_drafts_are_left_out(client, school, team, day, db_session):
    exam = create(client, school, day, kind="exam", starts=-5, ends=120, duration=60)
    create(client, school, day, kind="assignment", starts=-5, ends=3000, publish=False, title="Hidden draft")
    db_session.add(AssessmentAttempt(assessment_id=exam["id"], user_id=team["zed"].id, started_at=at(0), deadline_at=at(0) + timedelta(hours=1)))
    db_session.commit()
    rows = report(client, school)["assessments"]
    assert [(x["title"], x["participants"], x["avg_percent"]) for x in rows] == [("Midterm", 1, 0.0)]  # started, answered nothing: 0%


def test_nobody_took_part_gives_no_average(client, school, team, day):
    create(client, school, day, kind="assignment", starts=-5, ends=3000)
    row = report(client, school)["assessments"][0]
    assert (row["participants"], row["avg_percent"]) == (0, None)


# ---------------------------------------------------------------- CSV
def read_csv(res):
    assert res.status_code == 200, res.text
    return list(csv.reader(io.StringIO(res.text.lstrip("\ufeff"))))


def test_csv_has_one_row_per_student(client, school, team, day, db_session):
    _, lessons = course_with_lessons(client, school["teacher"], count=2)
    lesson_done(db_session, team["s1"], lessons[0], at(0))
    add_sub(db_session, team["s1"], school["p1"]["id"], "accepted", when=at(0))
    res = client.get(f"{API}/reports/batches/{school['batch']['id']}/export", headers=school["teacher"])
    assert res.headers["content-type"].startswith("text/csv") and res.text.startswith("\ufeff")
    assert f"batch-{school['batch']['id']}-progress.csv" in res.headers["content-disposition"]
    rows = read_csv(res)
    assert rows[0] == ["Name", "Email", "Lessons completed", "Lessons in courses", "Completion %", "Problems solved",
                       "Submissions (30 days)", "AI helper requests (30 days)", "Last active", "Days since last activity", "Status"]
    assert rows[1] == ["amy adams", "amy@x.com", "0", "2", "0.0", "0", "0", "0", "Never", "", "never_active"]
    assert rows[2] == ["student1", "student1@x.com", "1", "2", "50.0", "1", "1", "0", "2026-12-10", "0", "active"]


def test_csv_defuses_spreadsheet_formulas_and_needs_the_right_role(client, school, team, day, db_session):
    team["zed"].name = '=HYPERLINK("http://bad.example","click")'
    db_session.commit()
    rows = read_csv(client.get(f"{API}/reports/batches/{school['batch']['id']}/export", headers=school["teacher"]))
    assert not any(cell.startswith(("=", "+", "-", "@")) for row in rows for cell in row)
    assert any(cell.startswith("'=HYPERLINK") for row in rows for cell in row)
    assert client.get(f"{API}/reports/batches/{school['batch']['id']}/export", headers=school["student"]).status_code == 403


# ---------------------------------------------------------------- one student, as the teacher sees it
def test_a_teacher_can_open_the_dashboard_of_a_student_in_their_batch(client, school, team, day, db_session):
    ai_request(db_session, team["s1"], school["p1"]["id"], when=at(1))
    add_sub(db_session, team["s1"], school["p1"]["id"], "accepted", when=at(0))
    res = client.get(f"{API}/reports/students/{team['s1'].id}", headers=school["teacher"])
    assert res.status_code == 200
    body = res.json()
    assert (body["name"], body["email"], body["accepted_submissions"], body["ai_requests_30d"]) == ("student1", "student1@x.com", 1, 1)


def test_the_teacher_sees_real_exam_results_that_the_student_does_not(client, school, team, day, db_session):
    exam = create(client, school, day, kind="exam", starts=-5, ends=120, duration=60, problems=[(school["p1"]["id"], 10)])
    add_sub(db_session, team["s1"], school["p1"]["id"], "accepted", assessment_id=exam["id"], when=day.at(minutes=10))
    day.advance(minutes=130)
    teacher_view = client.get(f"{API}/reports/students/{team['s1'].id}", headers=school["teacher"]).json()
    student_view = client.get(f"{API}/reports/me", headers=school["student"]).json()
    assert teacher_view["accepted_submissions"] == 1 and teacher_view["recent"][0]["verdict"] == "accepted"
    assert student_view["accepted_submissions"] == 0 and student_view["recent"][0]["hidden"] is True


def test_who_may_open_which_student(client, school, team, day, login):
    url = lambda user: f"{API}/reports/students/{user.id}"
    outsider = school["outsider_user"]  # a student of the college who is in no batch of teacher1
    assert client.get(url(team["s1"]), headers=school["teacher"]).status_code == 200
    assert client.get(url(outsider), headers=school["teacher"]).status_code == 404
    assert client.get(url(outsider), headers=school["admin"]).status_code == 200  # an admin sees the whole college
    assert client.get(url(team["s1"]), headers=login(school["world"]["teacher1b"])).status_code == 404
    assert client.get(url(team["s1"]), headers=login(school["world"]["admin2"])).status_code == 404
    assert client.get(url(school["world"]["teacher1"]), headers=school["admin"]).status_code == 404  # only students have dashboards
    assert client.get(url(team["s1"]), headers=school["student"]).status_code == 403
    assert client.get(f"{API}/reports/students/9999", headers=school["admin"]).status_code == 404
