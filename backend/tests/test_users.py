import pytest


def new_user(role, email, **extra):
    return {"name": "New Person", "email": email, "password": "password123", "role": role, **extra}


# ---------- who can create whom ----------
def test_super_admin_creates_college_admin(client, world, login):
    res = client.post(
        "/api/v1/users",
        headers=login(world["super"]),
        json=new_user("admin", "newadmin@x.com", college_id=world["c1"].id),
    )
    assert res.status_code == 201
    assert res.json()["role"] == "admin"
    assert res.json()["college_id"] == world["c1"].id


def test_super_admin_must_say_which_college(client, world, login):
    res = client.post("/api/v1/users", headers=login(world["super"]), json=new_user("admin", "a@x.com"))
    assert res.status_code == 422


def test_super_admin_cannot_create_another_super_admin_through_api(client, world, login):
    res = client.post(
        "/api/v1/users",
        headers=login(world["super"]),
        json=new_user("super_admin", "boss@x.com", college_id=world["c1"].id),
    )
    assert res.status_code == 403


def test_admin_creates_teacher_and_student_in_own_college(client, world, login):
    headers = login(world["admin1"])
    for role in ("teacher", "student"):
        res = client.post("/api/v1/users", headers=headers, json=new_user(role, f"{role}-new@x.com"))
        assert res.status_code == 201
        assert res.json()["college_id"] == world["c1"].id


def test_admin_cannot_put_a_user_in_another_college(client, world, login):
    res = client.post(
        "/api/v1/users",
        headers=login(world["admin1"]),
        json=new_user("student", "sneaky@x.com", college_id=world["c2"].id),
    )
    assert res.status_code == 201
    assert res.json()["college_id"] == world["c1"].id  # college_id from the request is ignored


@pytest.mark.parametrize(
    "actor,role",
    [("admin1", "admin"), ("teacher1", "teacher"), ("teacher1", "admin"), ("student1", "student")],
)
def test_people_cannot_create_roles_above_their_level(client, world, login, actor, role):
    res = client.post("/api/v1/users", headers=login(world[actor]), json=new_user(role, "x1@x.com"))
    assert res.status_code == 403


def test_teacher_creates_student_in_own_batch(client, world, login):
    headers = login(world["teacher1"])
    batch = client.post("/api/v1/batches", headers=headers, json={"name": "CSE Sem 3"}).json()
    res = client.post(
        "/api/v1/users", headers=headers, json=new_user("student", "s-new@x.com", batch_id=batch["id"])
    )
    assert res.status_code == 201
    members = client.get(f"/api/v1/batches/{batch['id']}/members", headers=headers).json()
    assert [m["email"] for m in members] == ["s-new@x.com"]


def test_teacher_cannot_add_student_to_another_teachers_batch(client, world, login):
    other = client.post("/api/v1/batches", headers=login(world["teacher1b"]), json={"name": "Other"}).json()
    res = client.post(
        "/api/v1/users",
        headers=login(world["teacher1"]),
        json=new_user("student", "s2@x.com", batch_id=other["id"]),
    )
    assert res.status_code == 404
    # and the student must not be left half-created
    listing = client.get("/api/v1/users", headers=login(world["teacher1"])).json()
    assert "s2@x.com" not in [u["email"] for u in listing]


def test_only_students_go_into_batches(client, world, login):
    headers = login(world["admin1"])
    batch = client.post("/api/v1/batches", headers=headers, json={"name": "B"}).json()
    res = client.post("/api/v1/users", headers=headers, json=new_user("teacher", "t@x.com", batch_id=batch["id"]))
    assert res.status_code == 422


def test_duplicate_email_and_weak_password(client, world, login):
    headers = login(world["admin1"])
    assert client.post("/api/v1/users", headers=headers, json=new_user("student", "student2@x.com")).status_code == 409
    weak = new_user("student", "weak@x.com", password="short")
    assert client.post("/api/v1/users", headers=headers, json=weak).status_code == 422
    bad_email = new_user("student", "not-an-email")
    assert client.post("/api/v1/users", headers=headers, json=bad_email).status_code == 422


def test_created_user_can_log_in(client, world, login):
    client.post("/api/v1/users", headers=login(world["admin1"]), json=new_user("student", "fresh@x.com"))
    res = client.post("/api/v1/auth/login", json={"email": "fresh@x.com", "password": "password123"})
    assert res.status_code == 200


# ---------- listing ----------
def test_teacher_lists_only_students_of_own_college(client, world, login):
    res = client.get("/api/v1/users", headers=login(world["teacher1"]))
    assert res.status_code == 200
    assert [u["email"] for u in res.json()] == ["student1@x.com"]


def test_admin_lists_only_own_college(client, world, login):
    emails = {u["email"] for u in client.get("/api/v1/users", headers=login(world["admin1"])).json()}
    assert emails == {
        "admin1@x.com", "teacher1@x.com", "teacher1b@x.com", "student1@x.com",
    }
    only_teachers = client.get("/api/v1/users?role=teacher", headers=login(world["admin1"])).json()
    assert {u["email"] for u in only_teachers} == {"teacher1@x.com", "teacher1b@x.com"}


def test_admin_cannot_peek_at_another_college_with_filter(client, world, login):
    res = client.get(f"/api/v1/users?college_id={world['c2'].id}", headers=login(world["admin1"]))
    assert all(u["college_id"] == world["c1"].id for u in res.json())


def test_super_admin_sees_everyone_and_can_filter(client, world, login):
    headers = login(world["super"])
    assert len(client.get("/api/v1/users", headers=headers).json()) == 8  # all users in the test world
    only_c2 = client.get(f"/api/v1/users?college_id={world['c2'].id}", headers=headers).json()
    assert {u["email"] for u in only_c2} == {"admin2@x.com", "teacher2@x.com", "student2@x.com"}


def test_students_cannot_list_users(client, world, login):
    assert client.get("/api/v1/users", headers=login(world["student1"])).status_code == 403


# ---------- update / disable ----------
def test_admin_disables_a_student(client, world, login):
    res = client.patch(
        f"/api/v1/users/{world['student1'].id}", headers=login(world["admin1"]), json={"is_active": False}
    )
    assert res.status_code == 200
    assert res.json()["is_active"] is False
    login_try = client.post("/api/v1/auth/login", json={"email": "student1@x.com", "password": "password123"})
    assert login_try.status_code == 403


def test_admin_cannot_touch_other_college_or_themselves(client, world, login):
    headers = login(world["admin1"])
    assert client.patch(f"/api/v1/users/{world['student2'].id}", headers=headers, json={"is_active": False}).status_code == 404
    assert client.patch(f"/api/v1/users/{world['admin1'].id}", headers=headers, json={"is_active": False}).status_code == 404
    assert client.patch(f"/api/v1/users/{world['admin2'].id}", headers=headers, json={"is_active": False}).status_code == 404


def test_teacher_cannot_disable_students(client, world, login):
    res = client.patch(
        f"/api/v1/users/{world['student1'].id}", headers=login(world["teacher1"]), json={"is_active": False}
    )
    assert res.status_code == 403


def test_super_admin_cannot_be_changed_by_college_admin(client, world, login):
    res = client.patch(f"/api/v1/users/{world['super'].id}", headers=login(world["admin1"]), json={"is_active": False})
    assert res.status_code == 404


# ---------- password reset ----------
def test_teacher_resets_student_password(client, world, login):
    res = client.post(f"/api/v1/users/{world['student1'].id}/reset-password", headers=login(world["teacher1"]))
    assert res.status_code == 200
    temp = res.json()["temp_password"]
    old = client.post("/api/v1/auth/login", json={"email": "student1@x.com", "password": "password123"})
    new = client.post("/api/v1/auth/login", json={"email": "student1@x.com", "password": temp})
    assert old.status_code == 401
    assert new.status_code == 200


def test_reset_password_respects_roles_and_colleges(client, world, login):
    teacher = login(world["teacher1"])
    assert client.post(f"/api/v1/users/{world['teacher1b'].id}/reset-password", headers=teacher).status_code == 404
    assert client.post(f"/api/v1/users/{world['student2'].id}/reset-password", headers=teacher).status_code == 404
    assert client.post(f"/api/v1/users/{world['student1'].id}/reset-password", headers=login(world["student1"])).status_code == 403
    admin = login(world["admin1"])
    assert client.post(f"/api/v1/users/{world['teacher1'].id}/reset-password", headers=admin).status_code == 200


# ---------- bulk ----------
def test_bulk_create_students_into_a_batch(client, world, login):
    headers = login(world["teacher1"])
    batch = client.post("/api/v1/batches", headers=headers, json={"name": "Bulk"}).json()
    payload = {
        "batch_id": batch["id"],
        "students": [
            {"name": "A One", "email": "a1@x.com"},
            {"name": "B Two", "email": "b2@x.com"},
            {"name": "A Again", "email": "A1@x.com"},  # repeated in the list (different case)
            {"name": "Old", "email": "student1@x.com"},  # already registered
        ],
    }
    res = client.post("/api/v1/users/bulk", headers=headers, json=payload)
    assert res.status_code == 201
    results = res.json()
    assert len(results) == 4
    created = [r for r in results if r["temp_password"]]
    assert {r["email"] for r in created} == {"a1@x.com", "b2@x.com"}
    assert [r["error"] for r in results if r["error"]] == ["Repeated in this list.", "Email already registered."]
    rows = {r["email"]: r for r in created}
    members = client.get(f"/api/v1/batches/{batch['id']}/members", headers=headers).json()
    assert {m["email"] for m in members} == {"a1@x.com", "b2@x.com"}
    # the temporary password really works
    ok = client.post("/api/v1/auth/login", json={"email": "a1@x.com", "password": rows["a1@x.com"]["temp_password"]})
    assert ok.status_code == 200


def test_bulk_needs_staff_and_a_usable_batch(client, world, login):
    payload = {"students": [{"name": "A", "email": "a@x.com"}]}
    assert client.post("/api/v1/users/bulk", headers=login(world["student1"]), json=payload).status_code == 403
    other = client.post("/api/v1/batches", headers=login(world["teacher1b"]), json={"name": "Other"}).json()
    res = client.post("/api/v1/users/bulk", headers=login(world["teacher1"]), json={**payload, "batch_id": other["id"]})
    assert res.status_code == 404
