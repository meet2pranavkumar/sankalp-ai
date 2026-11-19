import pytest

from app.models import Lesson, LessonProgress, Unit


def make_course(client, headers, title="Intro to C", **extra):
    res = client.post("/api/v1/courses", headers=headers, json={"title": title, **extra})
    assert res.status_code == 201, res.text
    return res.json()


def add_unit(client, headers, course_id, title="Unit"):
    res = client.post(f"/api/v1/courses/{course_id}/units", headers=headers, json={"title": title})
    assert res.status_code == 201, res.text
    return res.json()


def add_lesson(client, headers, unit_id, title="Lesson", content="Hello **world**", **extra):
    res = client.post(
        f"/api/v1/units/{unit_id}/lessons", headers=headers, json={"title": title, "content_md": content, **extra}
    )
    assert res.status_code == 201, res.text
    return res.json()


def publish(client, headers, course_id, value=True):
    res = client.patch(f"/api/v1/courses/{course_id}", headers=headers, json={"is_published": value})
    assert res.status_code == 200, res.text
    return res.json()


@pytest.fixture()
def built(client, world, login):
    """A published course by teacher1 with 2 units and 3 lessons: u1=[A,B], u2=[C]."""
    t = login(world["teacher1"])
    course = make_course(client, t)
    u1 = add_unit(client, t, course["id"], "Basics")["units"][0]
    add_lesson(client, t, u1["id"], "A")
    c = add_lesson(client, t, u1["id"], "B")
    u2 = add_unit(client, t, course["id"], "Loops")["units"][1]
    c = add_lesson(client, t, u2["id"], "C")
    publish(client, t, course["id"])
    return client.get(f"/api/v1/courses/{course['id']}", headers=t).json()


def lesson_ids(course):
    return [l["id"] for u in course["units"] for l in u["lessons"]]


# ---------- creating and seeing courses ----------
def test_teacher_creates_a_draft_course(client, world, login):
    c = make_course(client, login(world["teacher1"]), description="Learn C", language="c")
    assert c["is_published"] is False and c["is_shared"] is False and c["can_edit"] is True
    assert c["units"] == [] and c["total_lessons"] == 0


def test_students_cannot_create_courses(client, world, login):
    assert client.post("/api/v1/courses", headers=login(world["student1"]), json={"title": "X"}).status_code == 403


def test_bad_course_input_is_rejected(client, world, login):
    h = login(world["teacher1"])
    assert client.post("/api/v1/courses", headers=h, json={"title": ""}).status_code == 422
    assert client.post("/api/v1/courses", headers=h, json={"title": "X", "language": "cobol"}).status_code == 422


def test_drafts_are_private_to_their_authors(client, world, login):
    c = make_course(client, login(world["teacher1"]))
    url = f"/api/v1/courses/{c['id']}"
    for key in ("teacher1", "admin1", "super"):
        assert client.get(url, headers=login(world[key])).status_code == 200, key
    for key in ("student1", "teacher1b", "student2", "teacher2", "admin2"):
        assert client.get(url, headers=login(world[key])).status_code == 404, key
    assert client.get("/api/v1/courses", headers=login(world["student1"])).json() == []


def test_publishing_shows_the_course_to_the_college_only(client, world, login, built):
    for key in ("student1", "teacher1b"):
        assert [c["id"] for c in client.get("/api/v1/courses", headers=login(world[key])).json()] == [built["id"]]
    for key in ("student2", "teacher2"):
        assert client.get("/api/v1/courses", headers=login(world[key])).json() == []
        assert client.get(f"/api/v1/courses/{built['id']}", headers=login(world[key])).status_code == 404


def test_unpublishing_hides_it_again(client, world, login, built):
    publish(client, login(world["teacher1"]), built["id"], False)
    assert client.get(f"/api/v1/courses/{built['id']}", headers=login(world["student1"])).status_code == 404


def test_only_authors_can_change_a_course(client, world, login, built):
    url = f"/api/v1/courses/{built['id']}"
    assert client.patch(url, headers=login(world["teacher1"]), json={"title": "New name"}).json()["title"] == "New name"
    assert client.patch(url, headers=login(world["admin1"]), json={"description": "By admin"}).status_code == 200
    assert client.patch(url, headers=login(world["teacher1b"]), json={"title": "Hack"}).status_code == 403
    assert client.patch(url, headers=login(world["student1"]), json={"title": "Hack"}).status_code == 403
    assert client.patch(url, headers=login(world["teacher2"]), json={"title": "Hack"}).status_code == 404


# ---------- shared courses ----------
def test_shared_course_is_read_only_for_colleges(client, world, login):
    owner = login(world["super"])
    shared = make_course(client, owner, title="Starter C")
    assert shared["is_shared"] is True
    unit = add_unit(client, owner, shared["id"])["units"][0]
    add_lesson(client, owner, unit["id"])
    publish(client, owner, shared["id"])
    for key in ("student1", "teacher1", "student2", "admin2"):
        got = client.get(f"/api/v1/courses/{shared['id']}", headers=login(world[key]))
        assert got.status_code == 200 and got.json()["can_edit"] is False, key
    for key in ("teacher1", "admin1"):
        assert client.patch(f"/api/v1/courses/{shared['id']}", headers=login(world[key]), json={"title": "X"}).status_code == 403
        assert client.post(f"/api/v1/courses/{shared['id']}/units", headers=login(world[key]), json={"title": "X"}).status_code == 403
        assert client.delete(f"/api/v1/courses/{shared['id']}", headers=login(world[key])).status_code == 403


def test_unpublished_shared_course_is_hidden_from_colleges(client, world, login):
    shared = make_course(client, login(world["super"]))
    assert client.get(f"/api/v1/courses/{shared['id']}", headers=login(world["teacher1"])).status_code == 404


# ---------- units ----------
def test_units_can_be_added_renamed_reordered_and_deleted(client, world, login):
    t = login(world["teacher1"])
    course = make_course(client, t)
    for name in ("One", "Two", "Three"):
        course = add_unit(client, t, course["id"], name)
    ids = [u["id"] for u in course["units"]]
    assert [u["title"] for u in course["units"]] == ["One", "Two", "Three"]

    renamed = client.patch(f"/api/v1/units/{ids[0]}", headers=t, json={"title": "Uno"}).json()
    assert renamed["units"][0]["title"] == "Uno"

    reordered = client.put(f"/api/v1/courses/{course['id']}/units/order", headers=t, json={"ids": [ids[2], ids[0], ids[1]]}).json()
    assert [u["title"] for u in reordered["units"]] == ["Three", "Uno", "Two"]

    after_delete = client.delete(f"/api/v1/units/{ids[0]}", headers=t).json()
    assert [(u["title"], u["position"]) for u in after_delete["units"]] == [("Three", 1), ("Two", 2)]


@pytest.mark.parametrize("bad", [[999], [], "same-twice", "missing-one"])
def test_bad_reorder_requests_are_rejected(client, world, login, bad):
    t = login(world["teacher1"])
    course = make_course(client, t)
    add_unit(client, t, course["id"], "One")
    course = add_unit(client, t, course["id"], "Two")
    a, b = [u["id"] for u in course["units"]]
    ids = {"same-twice": [a, a], "missing-one": [a]}[bad] if isinstance(bad, str) else bad
    assert client.put(f"/api/v1/courses/{course['id']}/units/order", headers=t, json={"ids": ids}).status_code == 422


def test_strangers_cannot_edit_units(client, world, login, built):
    unit_id = built["units"][0]["id"]
    assert client.patch(f"/api/v1/units/{unit_id}", headers=login(world["teacher1b"]), json={"title": "X"}).status_code == 403
    assert client.patch(f"/api/v1/units/{unit_id}", headers=login(world["student1"]), json={"title": "X"}).status_code == 403
    assert client.patch(f"/api/v1/units/{unit_id}", headers=login(world["teacher2"]), json={"title": "X"}).status_code == 404
    assert client.patch("/api/v1/units/9999", headers=login(world["teacher1"]), json={"title": "X"}).status_code == 404
    assert client.delete(f"/api/v1/units/{unit_id}", headers=login(world["teacher2"])).status_code == 404


# ---------- lessons ----------
def test_lesson_page_has_content_and_neighbours(client, world, login, built):
    a, b, c = lesson_ids(built)
    s = login(world["student1"])
    mid = client.get(f"/api/v1/lessons/{b}", headers=s).json()
    assert mid["title"] == "B" and mid["content_md"] == "Hello **world**"
    assert (mid["prev_lesson_id"], mid["next_lesson_id"]) == (a, c)  # next crosses into the next unit
    assert mid["unit_title"] == "Basics" and mid["course_title"] == "Intro to C" and mid["can_edit"] is False
    first = client.get(f"/api/v1/lessons/{a}", headers=s).json()
    last = client.get(f"/api/v1/lessons/{c}", headers=s).json()
    assert first["prev_lesson_id"] is None and last["next_lesson_id"] is None


def test_lessons_follow_the_course_visibility_rules(client, world, login, built):
    a = lesson_ids(built)[0]
    assert client.get(f"/api/v1/lessons/{a}", headers=login(world["student2"])).status_code == 404
    assert client.get("/api/v1/lessons/9999", headers=login(world["student1"])).status_code == 404
    assert client.get(f"/api/v1/lessons/{a}").status_code == 401
    publish(client, login(world["teacher1"]), built["id"], False)
    assert client.get(f"/api/v1/lessons/{a}", headers=login(world["student1"])).status_code == 404


def test_author_edits_lesson_content_and_video(client, world, login, built):
    a = lesson_ids(built)[0]
    t = login(world["teacher1"])
    res = client.patch(f"/api/v1/lessons/{a}", headers=t, json={"title": "A2", "content_md": "# New", "video_url": "https://youtu.be/xyz"})
    assert res.status_code == 200
    assert (res.json()["title"], res.json()["content_md"], res.json()["video_url"]) == ("A2", "# New", "https://youtu.be/xyz")
    only_title = client.patch(f"/api/v1/lessons/{a}", headers=t, json={"title": "A3"}).json()
    assert only_title["content_md"] == "# New" and only_title["video_url"] == "https://youtu.be/xyz"  # untouched
    removed = client.patch(f"/api/v1/lessons/{a}", headers=t, json={"video_url": None}).json()
    assert removed["video_url"] is None


@pytest.mark.parametrize("url", ["ftp://files.example.com/x", "javascript:alert(1)", "youtube.com/watch"])
def test_video_links_must_be_web_links(client, world, login, built, url):
    a = lesson_ids(built)[0]
    assert client.patch(f"/api/v1/lessons/{a}", headers=login(world["teacher1"]), json={"video_url": url}).status_code == 422


def test_lesson_edit_permissions(client, world, login, built):
    a = lesson_ids(built)[0]
    body = {"title": "X"}
    assert client.patch(f"/api/v1/lessons/{a}", headers=login(world["teacher1b"]), json=body).status_code == 403
    assert client.patch(f"/api/v1/lessons/{a}", headers=login(world["student1"]), json=body).status_code == 403
    assert client.patch(f"/api/v1/lessons/{a}", headers=login(world["teacher2"]), json=body).status_code == 404  # other college
    assert client.patch(f"/api/v1/lessons/{a}", headers=login(world["student2"]), json=body).status_code == 403  # students cannot edit at all
    assert client.patch(f"/api/v1/lessons/{a}", headers=login(world["admin1"]), json=body).status_code == 200
    assert client.delete(f"/api/v1/lessons/{a}", headers=login(world["teacher1b"])).status_code == 403


def test_lessons_can_be_reordered_and_deleted(client, world, login, built):
    t = login(world["teacher1"])
    unit = built["units"][0]
    a, b = [l["id"] for l in unit["lessons"]]
    swapped = client.put(f"/api/v1/units/{unit['id']}/lessons/order", headers=t, json={"ids": [b, a]}).json()
    assert [l["title"] for l in swapped["units"][0]["lessons"]] == ["B", "A"]
    after = client.delete(f"/api/v1/lessons/{b}", headers=t).json()
    assert [(l["title"], l["position"]) for l in after["units"][0]["lessons"]] == [("A", 1)]
    assert client.get(f"/api/v1/lessons/{b}", headers=t).status_code == 404


def test_lesson_content_has_a_size_limit(client, world, login, built):
    unit_id = built["units"][0]["id"]
    res = client.post(f"/api/v1/units/{unit_id}/lessons", headers=login(world["teacher1"]), json={"title": "Big", "content_md": "x" * 60_000})
    assert res.status_code == 422


# ---------- progress ----------
def test_marking_lessons_complete_updates_progress(client, world, login, built):
    a, b, c = lesson_ids(built)
    s = login(world["student1"])
    assert client.get(f"/api/v1/courses/{built['id']}", headers=s).json()["completed_lessons"] == 0
    assert client.post(f"/api/v1/lessons/{a}/complete", headers=s).status_code == 204
    assert client.post(f"/api/v1/lessons/{a}/complete", headers=s).status_code == 204  # twice is fine
    client.post(f"/api/v1/lessons/{c}/complete", headers=s)
    course = client.get(f"/api/v1/courses/{built['id']}", headers=s).json()
    assert (course["completed_lessons"], course["total_lessons"]) == (2, 3)
    assert [l["completed"] for u in course["units"] for l in u["lessons"]] == [True, False, True]
    listed = client.get("/api/v1/courses", headers=s).json()[0]
    assert (listed["completed_lessons"], listed["total_lessons"]) == (2, 3)
    assert client.get(f"/api/v1/lessons/{a}", headers=s).json()["completed"] is True


def test_progress_is_personal(client, world, login, built, make_user):
    from app.models import Role

    a = lesson_ids(built)[0]
    client.post(f"/api/v1/lessons/{a}/complete", headers=login(world["student1"]))
    other = make_user("other@x.com", Role.student, world["c1"])
    assert client.get(f"/api/v1/courses/{built['id']}", headers=login(other)).json()["completed_lessons"] == 0


def test_a_lesson_can_be_marked_not_done_again(client, world, login, built):
    a = lesson_ids(built)[0]
    s = login(world["student1"])
    client.post(f"/api/v1/lessons/{a}/complete", headers=s)
    assert client.delete(f"/api/v1/lessons/{a}/complete", headers=s).status_code == 204
    assert client.delete(f"/api/v1/lessons/{a}/complete", headers=s).status_code == 204  # nothing to remove is fine
    assert client.get(f"/api/v1/courses/{built['id']}", headers=s).json()["completed_lessons"] == 0


def test_cannot_complete_lessons_you_cannot_see(client, world, login, built):
    a = lesson_ids(built)[0]
    assert client.post(f"/api/v1/lessons/{a}/complete", headers=login(world["student2"])).status_code == 404
    assert client.post("/api/v1/lessons/9999/complete", headers=login(world["student1"])).status_code == 404
    assert client.post(f"/api/v1/lessons/{a}/complete").status_code == 401


# ---------- duplicate ----------
def test_duplicating_the_shared_course_gives_a_college_copy(client, world, login, db_session):
    owner = login(world["super"])
    shared = make_course(client, owner, title="Starter C", description="Basics")
    unit = add_unit(client, owner, shared["id"], "Getting started")["units"][0]
    add_lesson(client, owner, unit["id"], "Hello", "print it", video_url="https://example.com/v")
    publish(client, owner, shared["id"])
    s = login(world["student1"])
    client.post(f"/api/v1/lessons/{client.get(f'/api/v1/courses/{shared['id']}', headers=s).json()['units'][0]['lessons'][0]['id']}/complete", headers=s)

    t = login(world["teacher1"])
    res = client.post(f"/api/v1/courses/{shared['id']}/duplicate", headers=t)
    assert res.status_code == 201
    copy = res.json()
    assert copy["title"] == "Starter C (copy)" and copy["is_published"] is False
    assert copy["is_shared"] is False and copy["can_edit"] is True
    assert [(u["title"], [l["title"] for l in u["lessons"]]) for u in copy["units"]] == [("Getting started", ["Hello"])]
    new_lesson = client.get(f"/api/v1/lessons/{copy['units'][0]['lessons'][0]['id']}", headers=t).json()
    assert new_lesson["content_md"] == "print it" and new_lesson["video_url"] == "https://example.com/v"
    # the copy is independent: editing it leaves the shared one alone, and progress was not copied
    client.patch(f"/api/v1/lessons/{new_lesson['id']}", headers=t, json={"content_md": "changed"})
    original = client.get(f"/api/v1/courses/{shared['id']}", headers=t).json()
    assert client.get(f"/api/v1/lessons/{original['units'][0]['lessons'][0]['id']}", headers=t).json()["content_md"] == "print it"
    assert copy["completed_lessons"] == 0


def test_who_can_duplicate(client, world, login, built):
    url = f"/api/v1/courses/{built['id']}/duplicate"
    assert client.post(url, headers=login(world["student1"])).status_code == 403
    assert client.post(url, headers=login(world["teacher2"])).status_code == 404  # other college cannot even see it
    assert client.post(url, headers=login(world["teacher1b"])).status_code == 201  # a colleague may copy a published course
    assert client.post("/api/v1/courses/9999/duplicate", headers=login(world["teacher1"])).status_code == 404


def test_cannot_duplicate_someone_elses_draft(client, world, login):
    draft = make_course(client, login(world["teacher1"]))
    assert client.post(f"/api/v1/courses/{draft['id']}/duplicate", headers=login(world["teacher1b"])).status_code == 404


# ---------- deleting ----------
def test_deleting_a_course_removes_everything_inside_it(client, world, login, built, db_session):
    a = lesson_ids(built)[0]
    client.post(f"/api/v1/lessons/{a}/complete", headers=login(world["student1"]))
    assert db_session.query(LessonProgress).count() == 1
    assert client.delete(f"/api/v1/courses/{built['id']}", headers=login(world["student1"])).status_code == 403
    assert client.delete(f"/api/v1/courses/{built['id']}", headers=login(world["teacher1"])).status_code == 204
    db_session.expire_all()
    assert db_session.query(Unit).count() == 0 and db_session.query(Lesson).count() == 0
    assert db_session.query(LessonProgress).count() == 0
    assert client.get(f"/api/v1/courses/{built['id']}", headers=login(world["student1"])).status_code == 404


def test_deleting_a_lesson_removes_its_progress(client, world, login, built, db_session):
    a = lesson_ids(built)[0]
    client.post(f"/api/v1/lessons/{a}/complete", headers=login(world["student1"]))
    client.delete(f"/api/v1/lessons/{a}", headers=login(world["teacher1"]))
    db_session.expire_all()
    assert db_session.query(LessonProgress).count() == 0


def test_course_list_is_sorted_and_flags_are_right(client, world, login):
    t = login(world["teacher1"])
    make_course(client, t, title="Zebra")
    make_course(client, t, title="Apple")
    titles = [c["title"] for c in client.get("/api/v1/courses", headers=t).json()]
    assert titles == ["Apple", "Zebra"]
