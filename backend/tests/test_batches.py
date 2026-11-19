def make_batch(client, headers, name="CSE Sem 3", **extra):
    res = client.post("/api/v1/batches", headers=headers, json={"name": name, "year": 2026, **extra})
    assert res.status_code == 201, res.text
    return res.json()


def test_teacher_and_admin_create_batches_but_students_cannot(client, world, login):
    assert make_batch(client, login(world["teacher1"]))["created_by"] == world["teacher1"].id
    assert make_batch(client, login(world["admin1"]), name="Admin batch")["college_id"] == world["c1"].id
    res = client.post("/api/v1/batches", headers=login(world["student1"]), json={"name": "Nope"})
    assert res.status_code == 403


def test_batch_year_is_checked(client, world, login):
    res = client.post("/api/v1/batches", headers=login(world["teacher1"]), json={"name": "Old", "year": 1900})
    assert res.status_code == 422


def test_each_role_sees_the_right_batches(client, world, login):
    t1, t1b, a1, t2 = (login(world[k]) for k in ("teacher1", "teacher1b", "admin1", "teacher2"))
    b1 = make_batch(client, t1, "Teacher1 batch")
    make_batch(client, t1b, "Teacher1b batch")
    make_batch(client, t2, "College2 batch")
    client.post(f"/api/v1/batches/{b1['id']}/members", headers=t1, json={"user_ids": [world["student1"].id]})

    assert [b["name"] for b in client.get("/api/v1/batches", headers=t1).json()] == ["Teacher1 batch"]
    assert {b["name"] for b in client.get("/api/v1/batches", headers=a1).json()} == {"Teacher1 batch", "Teacher1b batch"}
    assert [b["name"] for b in client.get("/api/v1/batches", headers=login(world["student1"])).json()] == ["Teacher1 batch"]
    assert client.get("/api/v1/batches", headers=login(world["student2"])).json() == []


def test_batch_visibility_for_single_batch(client, world, login):
    b = make_batch(client, login(world["teacher1"]))
    client.post(f"/api/v1/batches/{b['id']}/members", headers=login(world["teacher1"]), json={"user_ids": [world["student1"].id]})
    assert client.get(f"/api/v1/batches/{b['id']}", headers=login(world["student1"])).status_code == 200
    assert client.get(f"/api/v1/batches/{b['id']}", headers=login(world["admin1"])).status_code == 200
    # strangers get "not found", not "forbidden"
    for key in ("teacher1b", "student2", "teacher2", "admin2"):
        assert client.get(f"/api/v1/batches/{b['id']}", headers=login(world[key])).status_code == 404, key
    assert client.get("/api/v1/batches/9999", headers=login(world["teacher1"])).status_code == 404


def test_add_list_and_remove_members(client, world, login, make_user):
    from app.models import Role

    headers = login(world["teacher1"])
    b = make_batch(client, headers)
    extra = make_user("extra@x.com", Role.student, world["c1"])
    added = client.post(f"/api/v1/batches/{b['id']}/members", headers=headers, json={"user_ids": [world["student1"].id, extra.id]})
    assert added.status_code == 201 and len(added.json()) == 2
    again = client.post(f"/api/v1/batches/{b['id']}/members", headers=headers, json={"user_ids": [extra.id, extra.id]})
    assert again.status_code == 201 and again.json() == []  # nothing new, no error, no duplicates
    assert len(client.get(f"/api/v1/batches/{b['id']}/members", headers=headers).json()) == 2

    assert client.delete(f"/api/v1/batches/{b['id']}/members/{extra.id}", headers=headers).status_code == 204
    assert client.delete(f"/api/v1/batches/{b['id']}/members/{extra.id}", headers=headers).status_code == 404
    assert len(client.get(f"/api/v1/batches/{b['id']}/members", headers=headers).json()) == 1


def test_only_students_of_the_same_college_can_be_added(client, world, login):
    headers = login(world["teacher1"])
    b = make_batch(client, headers)
    for bad in (world["student2"], world["teacher1b"], world["admin1"]):
        res = client.post(f"/api/v1/batches/{b['id']}/members", headers=headers, json={"user_ids": [bad.id]})
        assert res.status_code == 404, bad.email


def test_teacher_cannot_change_another_teachers_batch(client, world, login):
    b = make_batch(client, login(world["teacher1b"]), "Not yours")
    mine = login(world["teacher1"])
    assert client.post(f"/api/v1/batches/{b['id']}/members", headers=mine, json={"user_ids": [world["student1"].id]}).status_code == 404
    assert client.get(f"/api/v1/batches/{b['id']}/members", headers=mine).status_code == 404
    assert client.delete(f"/api/v1/batches/{b['id']}/members/{world['student1'].id}", headers=mine).status_code == 404


def test_students_cannot_manage_members(client, world, login):
    teacher = login(world["teacher1"])
    b = make_batch(client, teacher)
    client.post(f"/api/v1/batches/{b['id']}/members", headers=teacher, json={"user_ids": [world["student1"].id]})
    student = login(world["student1"])
    assert client.get(f"/api/v1/batches/{b['id']}/members", headers=student).status_code == 403
    assert client.post(f"/api/v1/batches/{b['id']}/members", headers=student, json={"user_ids": [world["student1"].id]}).status_code == 403


def test_list_users_by_batch(client, world, login):
    teacher = login(world["teacher1"])
    b = make_batch(client, teacher)
    client.post(f"/api/v1/batches/{b['id']}/members", headers=teacher, json={"user_ids": [world["student1"].id]})
    res = client.get(f"/api/v1/users?batch_id={b['id']}", headers=teacher)
    assert [u["email"] for u in res.json()] == ["student1@x.com"]
    other = make_batch(client, login(world["teacher1b"]), "Someone else's")
    assert client.get(f"/api/v1/users?batch_id={other['id']}", headers=teacher).status_code == 404
