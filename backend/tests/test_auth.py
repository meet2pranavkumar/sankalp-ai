from app.models import Role


def test_login_success(client, world):
    res = client.post("/api/v1/auth/login", json={"email": "teacher1@x.com", "password": "password123"})
    assert res.status_code == 200
    body = res.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["role"] == "teacher"
    assert body["user"]["college_name"] == "College One"
    assert "password_hash" not in body["user"]


def test_login_email_is_case_insensitive(client, world):
    res = client.post("/api/v1/auth/login", json={"email": "Teacher1@X.com", "password": "password123"})
    assert res.status_code == 200


def test_wrong_password_and_unknown_email_look_the_same(client, world):
    wrong = client.post("/api/v1/auth/login", json={"email": "teacher1@x.com", "password": "nope-nope"})
    unknown = client.post("/api/v1/auth/login", json={"email": "nobody@x.com", "password": "password123"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_disabled_account_cannot_log_in(client, make_user, make_college):
    college = make_college()
    make_user("off@x.com", Role.student, college, active=False)
    res = client.post("/api/v1/auth/login", json={"email": "off@x.com", "password": "password123"})
    assert res.status_code == 403


def test_me_needs_a_valid_token(client, world, login):
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer junk"}).status_code == 401
    res = client.get("/api/v1/auth/me", headers=login(world["student1"]))
    assert res.status_code == 200
    assert res.json()["email"] == "student1@x.com"


def test_token_stops_working_when_user_is_disabled(client, world, login, db_session):
    headers = login(world["student1"])
    world["student1"].is_active = False
    db_session.commit()
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_change_password(client, world, login):
    headers = login(world["student1"])
    bad = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"current_password": "wrong-one", "new_password": "brand-new-pass"},
    )
    assert bad.status_code == 400
    ok = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"current_password": "password123", "new_password": "brand-new-pass"},
    )
    assert ok.status_code == 204
    old = client.post("/api/v1/auth/login", json={"email": "student1@x.com", "password": "password123"})
    new = client.post("/api/v1/auth/login", json={"email": "student1@x.com", "password": "brand-new-pass"})
    assert old.status_code == 401
    assert new.status_code == 200


def test_new_password_must_be_long_enough(client, world, login):
    res = client.post(
        "/api/v1/auth/change-password",
        headers=login(world["student1"]),
        json={"current_password": "password123", "new_password": "short"},
    )
    assert res.status_code == 422
