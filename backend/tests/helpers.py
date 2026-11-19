SAMPLE = {"input": "1 2\n", "expected_output": "3\n", "is_hidden": False}
HIDDEN = {"input": "10 20\n", "expected_output": "30\n", "is_hidden": True}


def problem_body(**changes):
    body = {
        "title": "Add two numbers",
        "statement_md": "Read two integers and print their sum.",
        "difficulty": "easy",
        "tags": ["Math", "basics"],
        "time_limit_ms": 1000,
        "memory_limit_mb": 128,
        "test_cases": [SAMPLE, HIDDEN],
    }
    body.update(changes)
    return body


def create_problem(client, headers, **changes):
    res = client.post("/api/v1/problems", headers=headers, json=problem_body(**changes))
    assert res.status_code == 201, res.text
    return res.json()
