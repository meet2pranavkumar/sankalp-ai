import pytest

from app.models import Submission
from app.services.assessments import user_has_active_exam
from tests.assess_helpers import API, correct, create, finished, iso, submit, wrong


@pytest.fixture()
def exam(client, school, clock):
    """A published exam: window open since 5 minutes ago for 2 hours, each student gets 60 minutes."""
    return create(client, school, clock, kind="exam", starts=-5, ends=120, duration=60)


def start(client, school, exam, who="student"):
    res = client.post(f"{API}/assessments/{exam['id']}/start", headers=school[who])
    assert res.status_code == 200, res.text
    return res.json()


def detail(client, school, exam, who="student"):
    return client.get(f"{API}/assessments/{exam['id']}", headers=school[who]).json()


def save_draft(client, school, exam, problem, code, language="python"):
    return client.put(
        f"{API}/assessments/{exam['id']}/problems/{problem['id']}/draft",
        headers=school["student"], json={"language": language, "source_code": code},
    )


def solved(client, school, title="Add two numbers", who="student"):
    """The green tick in the problem list, looked up by the problem's name."""
    listed = client.get(f"{API}/problems", headers=school[who]).json()
    return next(p["solved"] for p in listed if p["title"] == title)


def stored(db_session, exam):
    db_session.expire_all()
    return db_session.query(Submission).filter(Submission.assessment_id == exam["id"], Submission.kind == "submit").all()


# ---------------------------------------------------------------- starting
def test_questions_are_secret_until_the_student_presses_start(client, school, exam):
    d = detail(client, school, exam)
    assert d["status"] == "ready" and d["problems"] is None and d["attempt"] is None
    assert client.get(f"{API}/assessments/{exam['id']}/problems/{school['p1']['id']}", headers=school["student"]).status_code == 403
    res = submit(client, school["student"], exam["id"], school["p1"]["id"])
    assert res.status_code == 403 and "Start" in res.json()["detail"]


def test_start_gives_the_student_their_own_timer(client, school, clock, exam):
    d = start(client, school, exam)
    assert d["status"] == "in_progress"
    assert d["attempt"]["deadline_at"].startswith(clock.at(minutes=60).isoformat()[:19])
    assert d["server_now"].startswith(clock.now.isoformat()[:19])
    assert [p["title"] for p in d["problems"]] == ["Add two numbers", "Add again"]
    assert d["problems"][0]["score"] is None  # no marks while the exam is running


def test_starting_late_never_goes_past_the_end_of_the_window(client, school, clock):
    exam = create(client, school, clock, kind="exam", starts=-5, ends=20, duration=20)
    clock.advance(minutes=15)
    d = start(client, school, exam)
    assert d["attempt"]["deadline_at"].startswith(clock.at(minutes=5).isoformat()[:19])  # only 5 minutes left in the window


def test_pressing_start_twice_does_not_give_extra_time(client, school, clock, exam):
    first = start(client, school, exam)["attempt"]["deadline_at"]
    clock.advance(minutes=30)
    assert start(client, school, exam)["attempt"]["deadline_at"] == first


def test_cannot_start_before_the_window_or_after_it(client, school, clock):
    early = create(client, school, clock, kind="exam", starts=30, ends=150, duration=60)
    res = client.post(f"{API}/assessments/{early['id']}/start", headers=school["student"])
    assert res.status_code == 403 and "not started" in res.json()["detail"]
    late = create(client, school, clock, kind="exam", starts=-120, ends=10, duration=30)
    clock.advance(minutes=11)
    res = client.post(f"{API}/assessments/{late['id']}/start", headers=school["student"])
    assert res.status_code == 403 and "over" in res.json()["detail"]
    assert detail(client, school, late)["status"] == "missed"


def test_only_students_of_the_batch_can_start(client, school, exam):
    assert client.post(f"{API}/assessments/{exam['id']}/start", headers=school["outsider"]).status_code == 404
    assert client.post(f"{API}/assessments/{exam['id']}/start", headers=school["teacher"]).status_code == 403


def test_assignments_cannot_be_started(client, school, clock):
    a = create(client, school, clock, kind="assignment", starts=-5, ends=3000)
    assert client.post(f"{API}/assessments/{a['id']}/start", headers=school["student"]).status_code == 400


# ---------------------------------------------------------------- during the exam
def test_exam_verdicts_are_hidden_but_run_still_works(client, school, clock, exam, fake_judge):
    start(client, school, exam)
    fake_judge.respond = correct
    sub = finished(client, school["student"], submit(client, school["student"], exam["id"], school["p1"]["id"]))
    assert sub["hidden"] is True and sub["status"] == "done"
    for field in ("verdict", "passed_count", "total_count", "results", "stdout", "compile_output"):
        assert sub[field] is None, field
    # the student can still test their code with Run
    run = client.post(f"{API}/run", headers=school["student"], json={
        "language": "python", "source_code": "x", "stdin": "20 22", "problem_id": school["p1"]["id"], "assessment_id": exam["id"]})
    out = client.get(f"{API}/submissions/{run.json()['id']}", headers=school["student"]).json()
    assert out["hidden"] is False and out["stdout"] == "42\n" and out["verdict"] == "ok"
    # the exam's own list of answers is masked too, and no marks are shown
    listed = client.get(f"{API}/assessments/{exam['id']}/problems/{school['p1']['id']}/submissions", headers=school["student"]).json()
    assert len(listed) == 1 and listed[0]["hidden"] is True and listed[0]["verdict"] is None
    assert client.get(f"{API}/assessments/{exam['id']}/my-result", headers=school["student"]).json()["visible"] is False
    d = detail(client, school, exam)
    assert d["my_marks"] is None and all(p["score"] is None for p in d["problems"])


def test_the_teacher_still_sees_everything(client, school, clock, exam, fake_judge):
    start(client, school, exam)
    fake_judge.respond = correct
    res = submit(client, school["student"], exam["id"], school["p1"]["id"])
    seen = client.get(f"{API}/submissions/{res.json()['id']}", headers=school["teacher"]).json()
    assert seen["hidden"] is False and seen["verdict"] == "accepted"


def test_once_time_is_over_no_more_answers_are_taken(client, school, clock, exam, fake_judge):
    start(client, school, exam)
    clock.advance(minutes=61)
    res = submit(client, school["student"], exam["id"], school["p1"]["id"])
    assert res.status_code == 403 and "time is over" in res.json()["detail"]
    payload = {"language": "python", "source_code": "x", "problem_id": school["p1"]["id"], "assessment_id": exam["id"]}
    assert client.post(f"{API}/run", headers=school["student"], json=payload).status_code == 403
    assert save_draft(client, school, exam, school["p1"], "print(1)").status_code == 403
    assert detail(client, school, exam)["status"] == "finished"


def test_answer_just_before_the_deadline_is_accepted(client, school, clock, exam, fake_judge):
    start(client, school, exam)
    clock.advance(minutes=59, seconds=59)
    assert submit(client, school["student"], exam["id"], school["p1"]["id"]).status_code == 202


def test_finishing_early_closes_the_exam_for_that_student(client, school, clock, exam):
    start(client, school, exam)
    clock.advance(minutes=10)
    d = client.post(f"{API}/assessments/{exam['id']}/finish", headers=school["student"]).json()
    assert d["status"] == "finished" and d["attempt"]["finished_at"].startswith(clock.now.isoformat()[:19])
    assert submit(client, school["student"], exam["id"], school["p1"]["id"]).status_code == 403
    clock.advance(minutes=5)
    again = client.post(f"{API}/assessments/{exam['id']}/finish", headers=school["student"]).json()
    assert again["attempt"]["finished_at"] == d["attempt"]["finished_at"]  # finishing twice changes nothing


def test_cannot_finish_an_exam_you_did_not_start(client, school, exam):
    assert client.post(f"{API}/assessments/{exam['id']}/finish", headers=school["student"]).status_code == 409


def test_tab_switches_are_counted_while_the_exam_runs_and_never_block(client, school, clock, exam):
    url = f"{API}/assessments/{exam['id']}/tab-switch"
    assert client.post(url, headers=school["student"]).status_code == 204  # before starting: ignored
    start(client, school, exam)
    for _ in range(2):
        assert client.post(url, headers=school["student"]).status_code == 204
    client.post(f"{API}/assessments/{exam['id']}/finish", headers=school["student"])
    client.post(url, headers=school["student"])  # after finishing: ignored
    rows = client.get(f"{API}/assessments/{exam['id']}/results", headers=school["teacher"]).json()["rows"]
    assert rows[0]["tab_switches"] == 2
    assert submit(client, school["student"], exam["id"], school["p1"]["id"]).status_code == 403  # (finished, so refused for time, not for switching)


# ---------------------------------------------------------------- saved drafts are submitted when time ends
def test_saved_code_is_submitted_and_marked_when_time_runs_out(client, school, clock, exam, fake_judge, db_session):
    start(client, school, exam)
    assert save_draft(client, school, exam, school["p1"], "print('draft')").status_code == 200
    assert stored(db_session, exam) == []
    clock.advance(minutes=61)
    fake_judge.respond = correct
    d = detail(client, school, exam)  # the student opens the page after time is up
    assert d["status"] == "finished"
    subs = stored(db_session, exam)
    assert len(subs) == 1 and subs[0].source_code == "print('draft')" and subs[0].status == "done"
    assert detail(client, school, exam)["status"] == "finished" and len(stored(db_session, exam)) == 1  # not submitted twice
    rows = client.get(f"{API}/assessments/{exam['id']}/results", headers=school["teacher"]).json()["rows"]
    assert rows[0]["auto_marks"] == 10.0 and rows[0]["status"] == "finished"


def test_the_teacher_opening_results_also_collects_every_students_draft(client, school, clock, exam, fake_judge, db_session):
    start(client, school, exam)
    save_draft(client, school, exam, school["p2"], "print('p2')")
    clock.advance(minutes=90)  # the student never came back
    fake_judge.respond = correct
    rows = client.get(f"{API}/assessments/{exam['id']}/results", headers=school["teacher"]).json()["rows"]
    assert len(stored(db_session, exam)) == 1
    again = client.get(f"{API}/assessments/{exam['id']}/results", headers=school["teacher"]).json()["rows"]
    assert again[0]["auto_marks"] == 20.0 and len(stored(db_session, exam)) == 1


def test_code_that_was_already_submitted_is_not_submitted_again(client, school, clock, exam, fake_judge, db_session):
    start(client, school, exam)
    fake_judge.respond = correct
    save_draft(client, school, exam, school["p1"], "print(1)")
    clock.advance(minutes=1)
    submit(client, school["student"], exam["id"], school["p1"]["id"], code="print(1)")
    clock.advance(minutes=61)
    detail(client, school, exam)
    assert len(stored(db_session, exam)) == 1


def test_newer_unsent_code_is_submitted_after_an_older_answer(client, school, clock, exam, fake_judge, db_session):
    start(client, school, exam)
    fake_judge.respond = wrong
    submit(client, school["student"], exam["id"], school["p1"]["id"], code="print('old')")
    clock.advance(minutes=1)
    save_draft(client, school, exam, school["p1"], "print('better')")
    clock.advance(minutes=61)
    fake_judge.respond = correct
    detail(client, school, exam)
    codes = sorted(s.source_code for s in stored(db_session, exam))
    assert codes == ["print('better')", "print('old')"]
    rows = client.get(f"{API}/assessments/{exam['id']}/results", headers=school["teacher"]).json()["rows"]
    assert rows[0]["auto_marks"] == 10.0  # the better answer counts


def test_blank_drafts_are_ignored(client, school, clock, exam, db_session):
    start(client, school, exam)
    save_draft(client, school, exam, school["p1"], "   \n")
    clock.advance(minutes=61)
    detail(client, school, exam)
    assert stored(db_session, exam) == []


def test_finishing_early_also_submits_the_saved_code(client, school, clock, exam, fake_judge, db_session):
    start(client, school, exam)
    fake_judge.respond = correct
    save_draft(client, school, exam, school["p1"], "print(1)")
    clock.advance(minutes=5)
    client.post(f"{API}/assessments/{exam['id']}/finish", headers=school["student"])
    assert len(stored(db_session, exam)) == 1


def test_draft_rules(client, school, clock, exam):
    assert save_draft(client, school, exam, school["p1"], "x").status_code == 403  # not started
    start(client, school, exam)
    url = f"{API}/assessments/{exam['id']}/problems/{school['p1']['id']}/draft"
    assert client.get(url, headers=school["student"]).json() is None  # nothing saved yet
    save_draft(client, school, exam, school["p1"], "print('hello')", language="c")
    got = client.get(url, headers=school["student"]).json()
    assert (got["language"], got["source_code"]) == ("c", "print('hello')")
    from tests.helpers import create_problem

    outside = create_problem(client, school["teacher"], title="Elsewhere")
    assert save_draft(client, school, exam, outside, "x").status_code == 404
    assert save_draft(client, school, exam, school["p1"], "x" * 70_000).status_code in (413, 422)
    assert client.put(url, headers=school["outsider"], json={"language": "c", "source_code": "x"}).status_code == 404
    assert client.put(url, headers=school["teacher"], json={"language": "c", "source_code": "x"}).status_code == 403


def test_drafts_exist_only_for_exams(client, school, clock):
    a = create(client, school, clock, kind="assignment", starts=-5, ends=3000)
    res = client.put(f"{API}/assessments/{a['id']}/problems/{school['p1']['id']}/draft", headers=school["student"], json={"language": "c", "source_code": "x"})
    assert res.status_code == 400


# ---------------------------------------------------------------- exam problems stay secret
def test_exam_problems_are_hidden_from_the_normal_problem_pages(client, school, clock, exam):
    p1 = school["p1"]["id"]
    for who in ("student", "outsider"):
        titles = [p["title"] for p in client.get(f"{API}/problems", headers=school[who]).json()]
        assert "Add two numbers" not in titles, who
        assert client.get(f"{API}/problems/{p1}", headers=school[who]).status_code == 404, who
        run = client.post(f"{API}/run", headers=school[who], json={"language": "c", "source_code": "x", "problem_id": p1})
        assert run.status_code == 404, who
        assert client.post(f"{API}/submissions", headers=school[who], json={"problem_id": p1, "language": "c", "source_code": "x"}).status_code == 404
    assert client.get(f"{API}/problems/{p1}", headers=school["teacher"]).status_code == 200  # teachers always can


def test_the_problems_open_up_again_when_the_exam_window_is_over(client, school, clock, exam):
    clock.advance(minutes=121)
    assert client.get(f"{API}/problems/{school['p1']['id']}", headers=school["outsider"]).status_code == 200
    assert "Add two numbers" in [p["title"] for p in client.get(f"{API}/problems", headers=school["outsider"]).json()]


def test_assignment_problems_are_hidden_only_until_it_starts(client, school, clock):
    create(client, school, clock, kind="assignment", starts=30, ends=3000)
    p1 = school["p1"]["id"]
    assert client.get(f"{API}/problems/{p1}", headers=school["outsider"]).status_code == 404
    clock.advance(minutes=31)
    assert client.get(f"{API}/problems/{p1}", headers=school["outsider"]).status_code == 200


def test_a_draft_exam_also_protects_its_problems(client, school, clock):
    create(client, school, clock, kind="exam", publish=False)
    assert client.get(f"{API}/problems/{school['p1']['id']}", headers=school["outsider"]).status_code == 404


# ---------------------------------------------------------------- after the exam
def test_exam_results_do_not_leak_before_the_teacher_publishes(client, school, clock, exam, fake_judge):
    start(client, school, exam)
    fake_judge.respond = correct
    sid = submit(client, school["student"], exam["id"], school["p1"]["id"]).json()["id"]
    clock.advance(minutes=130)  # the window is over, so the problem is open again, but the results are still secret
    p1 = school["p1"]["id"]
    assert solved(client, school) is False  # no green tick
    listed = client.get(f"{API}/problems/{p1}/submissions", headers=school["student"]).json()
    assert listed[0]["hidden"] is True and listed[0]["verdict"] is None
    assert client.get(f"{API}/submissions/{sid}", headers=school["student"]).json()["verdict"] is None
    assert client.get(f"{API}/assessments/{exam['id']}/my-result", headers=school["student"]).json()["visible"] is False


def test_publishing_results_reveals_everything_to_the_student(client, school, clock, exam, fake_judge):
    start(client, school, exam)
    fake_judge.respond = correct
    sid = submit(client, school["student"], exam["id"], school["p1"]["id"]).json()["id"]
    clock.advance(minutes=130)
    client.patch(f"{API}/assessments/{exam['id']}", headers=school["teacher"], json={"results_published": True})
    mine = client.get(f"{API}/assessments/{exam['id']}/my-result", headers=school["student"]).json()
    assert (mine["visible"], mine["auto_marks"], mine["final_marks"], mine["total_marks"]) == (True, 10.0, 10.0, 30.0)
    assert [(p["marks"], p["possible"]) for p in mine["per_problem"]] == [(10.0, 10.0), (0.0, 20.0)]
    sub = client.get(f"{API}/submissions/{sid}", headers=school["student"]).json()
    assert sub["hidden"] is False and sub["verdict"] == "accepted"
    assert solved(client, school) is True
    assert detail(client, school, exam)["my_marks"] == 10.0


def test_publishing_results_first_collects_unsent_drafts(client, school, clock, exam, fake_judge, db_session):
    start(client, school, exam)
    fake_judge.respond = correct
    save_draft(client, school, exam, school["p1"], "print(1)")
    clock.advance(minutes=130)
    client.patch(f"{API}/assessments/{exam['id']}", headers=school["teacher"], json={"results_published": True})
    assert len(stored(db_session, exam)) == 1
    assert client.get(f"{API}/assessments/{exam['id']}/my-result", headers=school["student"]).json()["auto_marks"] == 10.0


def test_the_ai_helper_gate_is_closed_only_during_an_exam(client, school, clock, exam, db_session):
    user = school["student_user"]
    assert user_has_active_exam(db_session, user, clock.now) is False  # not started
    start(client, school, exam)
    assert user_has_active_exam(db_session, user, clock.now) is True
    clock.advance(minutes=30)
    assert user_has_active_exam(db_session, user, clock.now) is True
    clock.advance(minutes=31)
    assert user_has_active_exam(db_session, user, clock.now) is False  # time over
    other = client.post(f"{API}/assessments/{create(client, school, clock, kind='exam', starts=-5, ends=300, duration=60)['id']}/start", headers=school["student"])
    clock.advance(minutes=5)
    client.post(f"{API}/assessments/{other.json()['id']}/finish", headers=school["student"])
    assert user_has_active_exam(db_session, user, clock.now) is False  # finished early


# ---------------------------------------------------------------- gaps found by the coverage report
def test_an_exam_before_its_window_shows_as_upcoming(client, school, clock):
    early = create(client, school, clock, kind="exam", starts=30, ends=150, duration=60)
    assert detail(client, school, early)["status"] == "upcoming"


def test_results_show_who_is_writing_and_who_has_not_started(client, school, clock, exam, make_user):
    from app.models import Role

    zed = make_user("zed@x.com", Role.student, school["world"]["c1"], name="Zed")
    client.post(f"{API}/batches/{school['batch']['id']}/members", headers=school["teacher"], json={"user_ids": [zed.id]})
    start(client, school, exam)
    rows = client.get(f"{API}/assessments/{exam['id']}/results", headers=school["teacher"]).json()["rows"]
    assert {r["name"]: r["status"] for r in rows} == {"student1": "in_progress", "Zed": "not_started"}
    clock.advance(minutes=61)
    rows = client.get(f"{API}/assessments/{exam['id']}/results", headers=school["teacher"]).json()["rows"]
    assert {r["name"]: r["status"] for r in rows} == {"student1": "finished", "Zed": "not_started"}


def test_several_hidden_answers_are_all_masked_in_every_list(client, school, clock, exam, fake_judge):
    start(client, school, exam)
    fake_judge.respond = correct
    for _ in range(3):
        submit(client, school["student"], exam["id"], school["p1"]["id"])
    inside = client.get(f"{API}/assessments/{exam['id']}/problems/{school['p1']['id']}/submissions", headers=school["student"]).json()
    assert len(inside) == 3 and all(s["hidden"] and s["verdict"] is None for s in inside)
    clock.advance(minutes=130)  # the problem is open to practice again, its exam answers must stay masked
    outside = client.get(f"{API}/problems/{school['p1']['id']}/submissions", headers=school["student"]).json()
    assert len(outside) == 3 and all(s["hidden"] and s["verdict"] is None for s in outside)


def test_finalizing_twice_changes_nothing_the_second_time(client, school, clock, exam, db_session, fake_judge):
    from app.models import Assessment
    from app.services.assessments import finalize_attempt, get_attempt

    start(client, school, exam)
    save_draft(client, school, exam, school["p1"], "print(1)")
    clock.advance(minutes=61)
    a = db_session.get(Assessment, exam["id"])
    attempt = get_attempt(db_session, a.id, school["student_user"].id)
    assert len(finalize_attempt(db_session, a, attempt, clock.now)) == 1
    assert finalize_attempt(db_session, a, attempt, clock.now) == []
