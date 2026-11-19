NEW = {"name": "New Polytechnic", "city": "Dhanbad", "state": "Jharkhand", "code": "np01"}


def test_super_admin_creates_and_lists_colleges(client, world, login):
    headers = login(world["super"])
    res = client.post("/api/v1/colleges", headers=headers, json=NEW)
    assert res.status_code == 201
    assert res.json()["code"] == "NP01"  # code is saved in capital letters
    names = [c["name"] for c in client.get("/api/v1/colleges", headers=headers).json()]
    assert "New Polytechnic" in names


def test_duplicate_college_code_is_rejected(client, world, login):
    headers = login(world["super"])
    client.post("/api/v1/colleges", headers=headers, json=NEW)
    res = client.post("/api/v1/colleges", headers=headers, json={**NEW, "name": "Other"})
    assert res.status_code == 409


def test_other_roles_cannot_manage_colleges(client, world, login):
    for key in ("admin1", "teacher1", "student1"):
        headers = login(world[key])
        assert client.post("/api/v1/colleges", headers=headers, json=NEW).status_code == 403
        assert client.get("/api/v1/colleges", headers=headers).status_code == 403


def test_colleges_need_login(client):
    assert client.get("/api/v1/colleges").status_code == 401
