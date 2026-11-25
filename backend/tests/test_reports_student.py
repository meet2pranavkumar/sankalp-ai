from datetime import timedelta

import pytest

from app.core.config import get_settings
from app.models import AssessmentAttempt, Role
from tests.assess_helpers import create
from tests.helpers import create_problem
from tests.report_helpers import API, NOON, add_sub, at, course_with_lessons, lesson_done


def me(client, school, who="student"):
    res = client.get(f"{API}/reports/me", headers=school[who])
    assert res.status_code == 200, res.text
    return res.json()


def level(report, name):
    return next(x for x in report["problems"] if x["difficulty"] == name)


# ---------------------------------------------------------------- a student who has done nothing yet
def test_a_new_student_sees_zeros_not_errors(client, school, day):
    course_with_lessons(client, school["teacher"], count=4)
    r = me(client, school, "student")
    assert [(c["title"], c["completed_lessons"], c["total_lessons"], c["percent"]) for c in r["courses"]] == [("C Basics", 0, 4, 0.0)]
    assert [(x["difficulty"], x["solved"], x["total"]) for x in r["problems"]] == [("easy", 0, 2), ("medium", 0, 0), ("hard", 0, 0)]
    assert (r["streak_days"], r["active_days_30"], r["total_submissions"], r["accepted_submissions"]) == (0, 0, 0, 0)
    assert r["last_active_at"] is None and r["recent"] == [] and r["ai_requests_30d"] is None
    assert len(r["activity"]) == 30
    assert r["activity"][0]["date"] == "2026-11-11" and r["activity"][-1]["date"] == "2026-12-10"  # oldest first, ends today
    assert all((d["submissions"], d["accepted"], d["lessons"]) == (0, 0, 0) for d in r["activity"])


def test_staff_cannot_open_the_student_dashboard(client, school, day):
    for who in ("teacher", "admin"):
        assert client.get(f"{API}/reports/me", headers=school[who]).status_code == 403
    assert client.get(f"{API}/reports/me").status_code == 401


# ---------------------------------------------------------------- courses
def test_lessons_done_show_as_a_percentage(client, school, day, db_session):
    _, lessons = course_with_lessons(client, school["teacher"], count=4)
    lesson_done(db_session, school["student_user"], lessons[0])
    r = me(client, school)
    assert (r["courses"][0]["completed_lessons"], r["courses"][0]["percent"]) == (1, 25.0)


def test_only_courses_the_student_can_read_are_listed(client, school, day, login):
    course_with_lessons(client, school["teacher"], title="Published")
    course_with_lessons(client, school["teacher"], title="Draft", publish=False)
    course_with_lessons(client, login(school["world"]["teacher2"]), title="Other college")
    course_with_lessons(client, school["teacher"], title="Empty", count=0)  # a published course without lessons says nothing
    shared = course_with_lessons(client, login(school["world"]["super"]), title="Shared starter")
    assert [c["title"] for c in me(client, school)["courses"]] == ["Published", "Shared starter"]
    assert shared[0]["is_shared"] is True


# ---------------------------------------------------------------- problems solved
def test_solved_counts_each_problem_once_and_by_level(client, school, day, db_session):
    medium = create_problem(client, school["teacher"], title="Medium one", difficulty="medium")
    s = school["student_user"]
    add_sub(db_session, s, school["p1"]["id"], "accepted", when=at(3))
    add_sub(db_session, s, school["p1"]["id"], "accepted", when=at(2))  # the same problem again: still one
    add_sub(db_session, s, school["p2"]["id"], "wrong_answer", when=at(2))  # tried, not solved
    add_sub(db_session, s, medium["id"], "accepted", when=at(1))
    add_sub(db_session, s, school["p2"]["id"], "accepted", kind="run", when=at(1))  # a Run proves nothing
    r = me(client, school)
    assert [(x["difficulty"], x["solved"], x["total"]) for x in r["problems"]] == [("easy", 1, 2), ("medium", 1, 1), ("hard", 0, 0)]
    assert (r["total_submissions"], r["accepted_submissions"]) == (4, 3)  # Submit presses only, Run is not counted


def test_totals_leave_out_other_colleges_and_secret_exam_problems(client, school, day, login):
    create_problem(client, login(school["world"]["teacher2"]), title="Other college problem")
    assert level(me(client, school), "easy")["total"] == 2
    exam = create(client, school, day, kind="exam", starts=-5, ends=120, duration=60, problems=[(school["p2"]["id"], 10)])
    assert level(me(client, school), "easy")["total"] == 1  # p2 is a secret until the exam window is over
    day.advance(minutes=130)
    assert level(me(client, school), "easy")["total"] == 2


# ---------------------------------------------------------------- streak
@pytest.mark.parametrize(
    "days_ago,expected",
    [
        ([0, 1, 2], 3),  # today and the two days before
        ([1, 2, 3, 4], 4),  # nothing yet today: the day is not over, the streak lives
        ([0, 2, 3], 1),  # a gap yesterday
        ([2, 3], 0),  # two days ago is too long ago
        ([], 0),
        ([0], 1),
    ],
)
def test_streak_counts_days_in_a_row(client, school, day, db_session, days_ago, expected):
    for n in days_ago:
        add_sub(db_session, school["student_user"], school["p1"]["id"], "wrong_answer", when=at(n))
    assert me(client, school)["streak_days"] == expected


def test_runs_lessons_and_starting_an_exam_all_keep_a_streak_alive(client, school, day, db_session):
    _, lessons = course_with_lessons(client, school["teacher"])
    s = school["student_user"]
    add_sub(db_session, s, school["p1"]["id"], "ok", kind="run", when=at(0))  # a Run today
    lesson_done(db_session, s, lessons[0], at(1))  # a lesson yesterday
    exam = create(client, school, day, kind="exam", starts=-5, ends=120, duration=60)
    db_session.add(AssessmentAttempt(assessment_id=exam["id"], user_id=s.id, started_at=at(2), deadline_at=at(2) + timedelta(hours=1)))
    db_session.commit()
    r = me(client, school)
    assert (r["streak_days"], r["active_days_30"]) == (3, 3)


def test_days_are_counted_in_the_colleges_time_zone(client, school, day, db_session, monkeypatch):
    # 19:00 UTC on 9 December is 00:30 on 10 December in India (UTC+5:30)
    add_sub(db_session, school["student_user"], school["p1"]["id"], "accepted", when=at(1, hour=19))
    plain = me(client, school)
    assert plain["activity"][-2]["submissions"] == 1 and plain["activity"][-1]["submissions"] == 0  # UTC: yesterday
    monkeypatch.setattr(get_settings(), "report_utc_offset_minutes", 330)
    india = me(client, school)
    assert india["activity"][-1]["submissions"] == 1 and india["activity"][-2]["submissions"] == 0  # India: today


# ---------------------------------------------------------------- the 30 day graph and recent answers
def test_the_graph_counts_each_day(client, school, day, db_session):
    _, lessons = course_with_lessons(client, school["teacher"])
    s, p1 = school["student_user"], school["p1"]["id"]
    add_sub(db_session, s, p1, "accepted", when=at(0, 9))
    add_sub(db_session, s, p1, "wrong_answer", when=at(0, 11))
    add_sub(db_session, s, p1, "ok", kind="run", when=at(0, 8))
    lesson_done(db_session, s, lessons[0], at(5))
    lesson_done(db_session, s, lessons[1], at(5, 15))
    add_sub(db_session, s, p1, "accepted", when=at(29))  # the oldest day on the graph
    add_sub(db_session, s, p1, "accepted", when=at(30))  # one day too old
    by_date = {d["date"]: d for d in me(client, school)["activity"]}
    assert (by_date["2026-12-10"]["submissions"], by_date["2026-12-10"]["accepted"]) == (3, 1)
    assert by_date["2026-12-05"]["lessons"] == 2
    assert by_date["2026-11-11"]["submissions"] == 1 and "2026-11-10" not in by_date


def test_recent_answers_are_the_last_ten_submits_newest_first(client, school, day, db_session):
    s = school["student_user"]
    for n in range(12):
        add_sub(db_session, s, school["p1"]["id"], "accepted" if n % 3 == 0 else "wrong_answer", when=at(20 - n))
    add_sub(db_session, s, school["p2"]["id"], "ok", kind="run", when=at(0))  # runs are not answers
    r = me(client, school)
    assert len(r["recent"]) == 10
    times = [x["created_at"] for x in r["recent"]]
    assert times == sorted(times, reverse=True)
    assert all(x["title"] == "Add two numbers" and x["hidden"] is False for x in r["recent"])
    assert r["recent"][0]["verdict"] in ("accepted", "wrong_answer") and r["recent"][0]["total_count"] == 2
    assert r["last_active_at"].startswith("2026-12-10T10:00")  # the Run today is the latest activity


# ---------------------------------------------------------------- exam secrecy
def test_exam_results_stay_hidden_on_the_dashboard_until_published(client, school, day, db_session):
    s = school["student_user"]
    exam = create(client, school, day, kind="exam", starts=-5, ends=120, duration=60, problems=[(school["p1"]["id"], 10)])
    add_sub(db_session, s, school["p1"]["id"], "accepted", assessment_id=exam["id"], when=day.at(minutes=10))
    day.advance(minutes=130)  # the window is over, so the problem is open again, but the results are not public
    r = me(client, school)
    assert level(r, "easy")["solved"] == 0 and r["accepted_submissions"] == 0
    assert r["total_submissions"] == 1  # that a student answered is not a secret
    assert [(x["title"], x["verdict"], x["hidden"], x["problem_id"]) for x in r["recent"]] == [("Exam answer (result hidden)", None, True, None)]
    assert sum(d["accepted"] for d in r["activity"]) == 0 and sum(d["submissions"] for d in r["activity"]) == 1
    client.patch(f"{API}/assessments/{exam['id']}", headers=school["teacher"], json={"results_published": True})
    r = me(client, school)
    assert level(r, "easy")["solved"] == 1 and r["accepted_submissions"] == 1
    assert [(x["title"], x["verdict"], x["hidden"]) for x in r["recent"]] == [("Add two numbers", "accepted", False)]


def test_assignment_results_are_not_secret(client, school, day, db_session):
    a = create(client, school, day, kind="assignment", starts=-10, ends=3000, problems=[(school["p1"]["id"], 10)])
    add_sub(db_session, school["student_user"], school["p1"]["id"], "accepted", assessment_id=a["id"], when=at(0))
    assert level(me(client, school), "easy")["solved"] == 1
