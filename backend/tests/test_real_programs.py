"""End to end with REAL compilers and programs (the local judge). Skipped when a tool is missing.

This proves the whole chain works: API -> background job -> compile -> run -> grade -> saved verdict.
It does NOT test Judge0's sandbox. See deploy/judge0/README.md for checking that on your server.
"""
import shutil
import sys

import pytest

from app.main import app
from app.routers.submissions import judge_dependency
from app.services.judge.local import LocalJudge
from tests.helpers import create_problem

needs_gcc = pytest.mark.skipif(shutil.which("gcc") is None, reason="gcc not installed")
needs_gpp = pytest.mark.skipif(shutil.which("g++") is None, reason="g++ not installed")
needs_java = pytest.mark.skipif(
    shutil.which("javac") is None or shutil.which("java") is None, reason="JDK not installed"
)

C_SUM = '#include <stdio.h>\nint main(){long a,b;scanf("%ld %ld",&a,&b);printf("%ld\\n",a+b);return 0;}'
CPP_SUM = "#include <iostream>\nint main(){long long a,b;std::cin>>a>>b;std::cout<<a+b<<std::endl;}"
PY_SUM = "a, b = map(int, input().split())\nprint(a + b)"
JAVA_SUM = (
    "import java.util.Scanner;\n"
    "public class Main { public static void main(String[] x) {"
    " Scanner s = new Scanner(System.in); long a = s.nextLong(), b = s.nextLong();"
    " System.out.println(a + b); } }"
)


@pytest.fixture(autouse=True)
def real_judge(client):
    # Depends on `client` so this runs AFTER the client fixture installs the fake judge, and replaces it.
    judge = LocalJudge()
    app.dependency_overrides[judge_dependency] = lambda: judge
    yield judge


@pytest.fixture()
def problem(client, world, login):
    # a tight time limit keeps the infinite-loop test fast
    return create_problem(client, login(world["teacher1"]), time_limit_ms=300)


@pytest.fixture()
def student(world, login):
    return login(world["student1"])


def judged(client, headers, problem_id, language, code):
    res = client.post("/api/v1/submissions", headers=headers, json={"problem_id": problem_id, "language": language, "source_code": code})
    assert res.status_code == 202, res.text
    return client.get(f"/api/v1/submissions/{res.json()['id']}", headers=headers).json()


@needs_gcc
def test_c_correct_solution_is_accepted(client, problem, student):
    sub = judged(client, student, problem["id"], "c", C_SUM)
    assert (sub["verdict"], sub["passed_count"], sub["total_count"]) == ("accepted", 2, 2)


@needs_gcc
def test_c_wrong_answer(client, problem, student):
    code = C_SUM.replace("a+b", "a-b")
    sub = judged(client, student, problem["id"], "c", code)
    assert sub["verdict"] == "wrong_answer" and sub["passed_count"] == 0
    assert sub["results"][0]["actual"].strip() == "-1"  # the sample test shows what the program printed
    assert "hidden" in sub["results"][1] and "actual" not in sub["results"][1]


@needs_gcc
def test_c_passes_samples_but_fails_a_hidden_test(client, problem, student):
    code = '#include <stdio.h>\nint main(){long a,b;scanf("%ld %ld",&a,&b);printf("%ld\\n",a==1?a+b:0);return 0;}'
    sub = judged(client, student, problem["id"], "c", code)
    assert sub["verdict"] == "wrong_answer" and (sub["passed_count"], sub["total_count"]) == (1, 2)


@needs_gcc
def test_c_compile_error_shows_the_compiler_message(client, problem, student):
    sub = judged(client, student, problem["id"], "c", "int main( { return 0 }")
    assert sub["verdict"] == "compile_error" and "error" in sub["compile_output"]
    assert sub["status"] == "done"  # it is the student's mistake, not a judge failure


@needs_gcc
def test_c_infinite_loop_is_time_limit(client, problem, student):
    sub = judged(client, student, problem["id"], "c", "int main(){while(1){}}")
    assert sub["verdict"] == "time_limit" and sub["passed_count"] == 0


@needs_gcc
def test_c_crash_is_runtime_error(client, problem, student):
    sub = judged(client, student, problem["id"], "c", "int main(){int*p=0;*p=1;return 0;}")
    assert sub["verdict"] == "runtime_error"
    assert "signal" in sub["results"][0]["error"]


@needs_gcc
def test_c_nonzero_exit_is_runtime_error(client, problem, student):
    sub = judged(client, student, problem["id"], "c", "int main(){return 3;}")
    assert sub["verdict"] == "runtime_error"


@needs_gpp
def test_cpp_correct_solution(client, problem, student):
    assert judged(client, student, problem["id"], "cpp", CPP_SUM)["verdict"] == "accepted"


def test_python_correct_solution(client, problem, student):
    sub = judged(client, student, problem["id"], "python", PY_SUM)
    assert sub["verdict"] == "accepted" and sub["passed_count"] == 2


def test_python_exception_is_runtime_error_with_traceback(client, problem, student):
    sub = judged(client, student, problem["id"], "python", "print(1/0)")
    assert sub["verdict"] == "runtime_error"
    assert "ZeroDivisionError" in sub["results"][0]["error"]


def test_python_sleeping_forever_is_time_limit(client, problem, student):
    sub = judged(client, student, problem["id"], "python", "import time\ntime.sleep(60)")
    assert sub["verdict"] == "time_limit"


def test_python_syntax_error_is_runtime_error(client, problem, student):
    sub = judged(client, student, problem["id"], "python", "print(")
    assert sub["verdict"] == "runtime_error" and "SyntaxError" in sub["results"][0]["error"]


def test_output_flood_is_stopped(client, problem, student):
    sub = judged(client, student, problem["id"], "python", "while True:\n    print('x' * 100)")
    assert sub["verdict"] in ("runtime_error", "time_limit")
    assert len(sub["results"][0]["actual"]) < 2100


def test_run_with_custom_input(client, student):
    res = client.post("/api/v1/run", headers=student, json={"language": "python", "source_code": PY_SUM, "stdin": "20 22\n"})
    done = client.get(f"/api/v1/submissions/{res.json()['id']}", headers=student).json()
    assert done["verdict"] == "ok" and done["stdout"].strip() == "42"


@needs_gcc
def test_run_reports_compile_errors(client, student):
    res = client.post("/api/v1/run", headers=student, json={"language": "c", "source_code": "oops"})
    done = client.get(f"/api/v1/submissions/{res.json()['id']}", headers=student).json()
    assert done["verdict"] == "compile_error" and done["compile_output"]


@needs_java
def test_java_correct_solution(client, world, login, student):
    problem = create_problem(client, login(world["teacher1"]), time_limit_ms=2000)
    assert judged(client, student, problem["id"], "java", JAVA_SUM)["verdict"] == "accepted"


def test_local_judge_refuses_to_start_outside_development(monkeypatch):  # noqa: F811
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "app_env", "production")
    with pytest.raises(RuntimeError, match="not safe"):
        LocalJudge()
