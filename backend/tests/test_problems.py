import pytest

from tests.helpers import HIDDEN, SAMPLE, create_problem, problem_body


def test_teacher_creates_a_problem(client, world, login):
    p = create_problem(client, login(world["teacher1"]))
    assert p["college_id"] == world["c1"].id
    assert p["is_public"] is False and p["can_edit"] is True
    assert p["tags"] == ["math", "basics"]  # tags are cleaned
    assert [t["is_hidden"] for t in p["test_cases"]] == [False, True]  # the teacher sees every test


def test_students_cannot_create_problems(client, world, login):
    res = client.post("/api/v1/problems", headers=login(world["student1"]), json=problem_body())
    assert res.status_code == 403


@pytest.mark.parametrize(
    "changes",
    [
        {"test_cases": []},
        {"test_cases": [HIDDEN]},  # needs at least one sample the students can see
        {"title": ""},
        {"difficulty": "impossible"},
        {"time_limit_ms": 5},
        {"memory_limit_mb": 4000},
        {"tags": ["x" * 40]},
    ],
)
def test_bad_problems_are_rejected(client, world, login, changes):
    res = client.post("/api/v1/problems", headers=login(world["teacher1"]), json=problem_body(**changes))
    assert res.status_code == 422


def test_teacher_cannot_share_problems_with_other_colleges(client, world, login):
    res = client.post("/api/v1/problems", headers=login(world["teacher1"]), json=problem_body(is_public=True))
    assert res.status_code == 403


def test_platform_owner_problems_are_shared_with_everyone(client, world, login):
    p = create_problem(client, login(world["super"]))
    assert p["is_public"] is True and p["college_id"] is None
    for key in ("student1", "student2", "teacher2"):
        assert client.get(f"/api/v1/problems/{p['id']}", headers=login(world[key])).status_code == 200


def test_students_see_samples_only_and_never_hidden_tests(client, world, login):
    p = create_problem(client, login(world["teacher1"]))
    res = client.get(f"/api/v1/problems/{p['id']}", headers=login(world["student1"]))
    body = res.json()
    assert body["can_edit"] is False
    assert len(body["test_cases"]) == 1 and body["test_cases"][0]["is_hidden"] is False
    assert "30" not in res.text  # the hidden expected output is nowhere in the response


def test_problems_stay_inside_their_college(client, world, login):
    p = create_problem(client, login(world["teacher1"]))
    for key in ("student2", "teacher2", "admin2"):
        assert client.get(f"/api/v1/problems/{p['id']}", headers=login(world[key])).status_code == 404
    listed = client.get("/api/v1/problems", headers=login(world["student2"])).json()
    assert listed == []
    assert len(client.get("/api/v1/problems", headers=login(world["student1"])).json()) == 1
    assert client.get("/api/v1/problems/9999", headers=login(world["student1"])).status_code == 404


def test_who_can_edit(client, world, login):
    p = create_problem(client, login(world["teacher1"]))
    url = f"/api/v1/problems/{p['id']}"
    new = problem_body(title="Renamed", test_cases=[SAMPLE])
    assert client.put(url, headers=login(world["teacher1"]), json=new).status_code == 200
    assert client.put(url, headers=login(world["admin1"]), json=new).status_code == 200
    assert client.put(url, headers=login(world["teacher1b"]), json=new).status_code == 403  # same college, not the author
    assert client.put(url, headers=login(world["student1"]), json=new).status_code == 403
    assert client.put(url, headers=login(world["teacher2"]), json=new).status_code == 404  # other college
    assert client.put(url, headers=login(world["super"]), json=new).status_code == 200


def test_edit_replaces_the_test_cases(client, world, login):
    teacher = login(world["teacher1"])
    p = create_problem(client, teacher)
    new = problem_body(test_cases=[SAMPLE, {"input": "5 5", "expected_output": "10", "is_hidden": True}])
    updated = client.put(f"/api/v1/problems/{p['id']}", headers=teacher, json=new).json()
    assert [t["expected_output"] for t in updated["test_cases"]] == ["3\n", "10"]
    assert [t["position"] for t in updated["test_cases"]] == [1, 2]


def test_nobody_but_the_owner_edits_the_shared_bank(client, world, login):
    p = create_problem(client, login(world["super"]))
    for key in ("admin1", "teacher1"):
        assert client.put(f"/api/v1/problems/{p['id']}", headers=login(world[key]), json=problem_body()).status_code == 403


def test_list_filters(client, world, login):
    t = login(world["teacher1"])
    create_problem(client, t, title="Sum", difficulty="easy", tags=["math"])
    create_problem(client, t, title="Sort numbers", difficulty="medium", tags=["arrays", "sorting"])
    create_problem(client, t, title="Graph walk", difficulty="hard", tags=["graphs"])
    s = login(world["student1"])
    titles = lambda url: sorted(p["title"] for p in client.get(url, headers=s).json())
    assert titles("/api/v1/problems") == ["Graph walk", "Sort numbers", "Sum"]
    assert titles("/api/v1/problems?difficulty=medium") == ["Sort numbers"]
    assert titles("/api/v1/problems?tag=GRAPHS") == ["Graph walk"]
    assert titles("/api/v1/problems?q=sor") == ["Sort numbers"]


def test_languages_list_needs_no_login(client):
    res = client.get("/api/v1/languages")
    assert res.status_code == 200
    assert {l["key"] for l in res.json()} == {"c", "cpp", "java", "python"}
