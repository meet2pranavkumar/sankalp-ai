"""Checks our Judge0 client against a pretend Judge0 server that follows the official API docs."""
import base64
import json

import httpx
import pytest

from app.services.judge.base import JudgeJob, RunStatus
from app.services.judge.judge0 import Judge0Judge


def b64(text):
    return base64.b64encode(text.encode()).decode()


class FakeJudge0:
    """Pretends to be Judge0 CE 1.13.1. 'plan' says what each submission will finally return."""

    def __init__(self, plan=None, polls_before_done=2, queue_full_times=0, status_code=None):
        self.plan = plan or (lambda payload: {"status_id": 3, "stdout": b64("OK\n"), "time": "0.012", "memory": 3000})
        self.polls_before_done = polls_before_done
        self.queue_full_times = queue_full_times
        self.force_status = status_code
        self.posts: list[dict] = []
        self.requests: list[httpx.Request] = []
        self.created: dict[str, dict] = {}
        self.polls: dict[str, int] = {}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.force_status:
            return httpx.Response(self.force_status, json={"error": "nope"})
        if request.method == "POST" and request.url.path == "/submissions/batch":
            assert request.url.params["base64_encoded"] == "true"
            if self.queue_full_times > 0:
                self.queue_full_times -= 1
                return httpx.Response(503, json={"error": "queue is full"})
            body = json.loads(request.content)
            self.posts.append(body)
            tokens = []
            for payload in body["submissions"]:
                if payload["language_id"] == 0:
                    tokens.append({"language_id": ["language with id 0 doesn't exist"]})
                    continue
                token = f"tok-{len(self.created)}"
                self.created[token] = payload
                self.polls[token] = 0
                tokens.append({"token": token})
            return httpx.Response(201, json=tokens)
        if request.method == "GET" and request.url.path == "/submissions/batch":
            assert request.url.params["base64_encoded"] == "true"
            items = []
            for token in request.url.params["tokens"].split(","):
                self.polls[token] += 1
                if self.polls[token] <= self.polls_before_done:
                    items.append({"token": token, "status_id": 1 if self.polls[token] == 1 else 2})
                else:
                    items.append({"token": token, **self.plan(self.created[token])})
            return httpx.Response(200, json={"submissions": items})
        return httpx.Response(404)


def make_judge(fake, **kwargs):
    client = httpx.Client(base_url="http://judge0.test", transport=httpx.MockTransport(fake))
    return Judge0Judge("http://judge0.test", client=client, sleep=lambda s: None, **kwargs)


JOB = JudgeJob(language="python", source_code="print('hi')", stdin="1 2\n", time_limit_ms=1000, memory_limit_mb=128)


def test_happy_path_waits_for_queue_then_returns_output():
    fake = FakeJudge0(polls_before_done=2)
    out = make_judge(fake).run_jobs([JOB])
    assert out[0].status == RunStatus.ok
    assert out[0].stdout == "OK\n"
    assert out[0].time_ms == 12 and out[0].memory_kb == 3000
    assert fake.polls["tok-0"] == 3  # in queue, processing, done


def test_request_follows_the_documented_api_and_our_safety_rules():
    fake = FakeJudge0()
    make_judge(fake).run_jobs([JOB])
    sent = fake.posts[0]["submissions"][0]
    assert sent["language_id"] == 71  # Python 3.8.1
    assert base64.b64decode(sent["source_code"]).decode() == "print('hi')"
    assert base64.b64decode(sent["stdin"]).decode() == "1 2\n"
    assert sent["enable_network"] is False
    assert "expected_output" not in sent  # we compare outputs ourselves
    assert sent["cpu_time_limit"] == 3.0  # 1 second x 3 for Python
    assert sent["memory_limit"] == 128 * 1024
    assert sent["wall_time_limit"] > sent["cpu_time_limit"]


@pytest.mark.parametrize(
    "language,lang_id", [("c", 50), ("cpp", 54), ("java", 62), ("python", 71)]
)
def test_language_ids(language, lang_id):
    fake = FakeJudge0()
    make_judge(fake).run_jobs([JudgeJob(language=language, source_code="x")])
    assert fake.posts[0]["submissions"][0]["language_id"] == lang_id


def test_limits_never_go_above_what_judge0_accepts():
    fake = FakeJudge0()
    big = JudgeJob(language="python", source_code="x", time_limit_ms=10_000, memory_limit_mb=512)
    make_judge(fake, max_cpu_seconds=15, max_wall_seconds=20, max_memory_kb=256000).run_jobs([big])
    sent = fake.posts[0]["submissions"][0]
    assert sent["cpu_time_limit"] == 15  # 10 s x 3 would have been 30, which Judge0 rejects
    assert sent["wall_time_limit"] == 20
    assert sent["memory_limit"] == 256000
    assert sent["wall_time_limit"] >= sent["cpu_time_limit"]


def test_java_gets_enough_memory_to_start():
    fake = FakeJudge0()
    make_judge(fake).run_jobs([JudgeJob(language="java", source_code="x", memory_limit_mb=64)])
    assert fake.posts[0]["submissions"][0]["memory_limit"] >= 262144


@pytest.mark.parametrize(
    "status_id,expected",
    [(3, RunStatus.ok), (4, RunStatus.ok), (5, RunStatus.time_limit), (6, RunStatus.compile_error),
     (7, RunStatus.runtime_error), (9, RunStatus.runtime_error), (11, RunStatus.runtime_error),
     (12, RunStatus.runtime_error), (13, RunStatus.internal_error), (14, RunStatus.internal_error)],
)
def test_status_mapping(status_id, expected):
    fake = FakeJudge0(plan=lambda p: {"status_id": status_id})
    assert make_judge(fake).run_jobs([JOB])[0].status == expected


def test_compile_error_text_and_runtime_error_text_are_decoded():
    def plan(payload):
        if "bad" in base64.b64decode(payload["source_code"]).decode():
            return {"status_id": 6, "compile_output": b64("main.c:1:1: error: boom")}
        return {"status_id": 11, "stderr": b64("Traceback: ZeroDivisionError"), "message": b64("NZEC")}

    fake = FakeJudge0(plan=plan)
    out = make_judge(fake).run_jobs([JudgeJob("c", "bad code"), JudgeJob("python", "1/0")])
    assert out[0].compile_output == "main.c:1:1: error: boom"
    assert "ZeroDivisionError" in out[1].stderr and out[1].message == "NZEC"


def test_non_utf8_output_does_not_crash():
    fake = FakeJudge0(plan=lambda p: {"status_id": 3, "stdout": base64.b64encode(b"\xff\xfe ok").decode()})
    assert "ok" in make_judge(fake).run_jobs([JOB])[0].stdout


def test_one_rejected_job_does_not_break_the_others():
    fake = FakeJudge0()
    judge = make_judge(fake)
    judge._payload = lambda job: {"language_id": 0 if job.source_code == "bad" else 71, "source_code": "", "stdin": ""}
    out = judge.run_jobs([JudgeJob("python", "good1"), JudgeJob("python", "bad"), JudgeJob("python", "good2")])
    assert [o.status for o in out] == [RunStatus.ok, RunStatus.internal_error, RunStatus.ok]
    assert "rejected" in out[1].message


def test_large_submissions_are_sent_in_batches_of_20_and_order_is_kept():
    fake = FakeJudge0(plan=lambda p: {"status_id": 3, "stdout": p["stdin"]}, polls_before_done=0)
    jobs = [JudgeJob("python", "x", stdin=str(i)) for i in range(45)]
    out = make_judge(fake).run_jobs(jobs)
    assert [len(p["submissions"]) for p in fake.posts] == [20, 20, 5]
    assert [o.stdout for o in out] == [str(i) for i in range(45)]  # client already decoded the base64


def test_queue_full_is_retried_then_succeeds():
    fake = FakeJudge0(queue_full_times=2)
    assert make_judge(fake).run_jobs([JOB])[0].status == RunStatus.ok


def test_queue_full_forever_gives_a_friendly_error():
    fake = FakeJudge0(queue_full_times=99)
    out = make_judge(fake).run_jobs([JOB])
    assert out[0].status == RunStatus.internal_error and "busy" in out[0].message


@pytest.mark.parametrize("code,word", [(401, "login"), (403, "login"), (500, "HTTP 500")])
def test_server_errors_become_internal_errors(code, word):
    out = make_judge(FakeJudge0(status_code=code)).run_jobs([JOB])
    assert out[0].status == RunStatus.internal_error and word in out[0].message


def test_unreachable_judge_is_reported_clearly():
    def boom(request):
        raise httpx.ConnectError("refused")

    out = make_judge(boom).run_jobs([JOB])
    assert out[0].status == RunStatus.internal_error and "not reachable" in out[0].message


def test_judge_that_never_finishes_times_out():
    fake = FakeJudge0(polls_before_done=10_000)
    out = make_judge(fake, timeout_seconds=0).run_jobs([JOB])
    assert out[0].status == RunStatus.internal_error and "too long" in out[0].message


def test_unknown_language_never_reaches_the_server():
    fake = FakeJudge0()
    out = make_judge(fake).run_jobs([JudgeJob("cobol", "x")])
    assert out[0].status == RunStatus.internal_error
    assert fake.requests == []


def test_auth_token_is_sent_in_the_header():
    fake = FakeJudge0()
    seen = {}

    def spy(request):
        seen.update(request.headers)
        return fake(request)

    client = httpx.Client(
        base_url="http://judge0.test", transport=httpx.MockTransport(spy), headers={"X-Auth-Token": "secret"}
    )
    Judge0Judge("http://judge0.test", auth_token="secret", client=client, sleep=lambda s: None).run_jobs([JOB])
    assert seen["x-auth-token"] == "secret"
