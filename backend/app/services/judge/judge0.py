"""Client for a Judge0 CE v1.13.1 server (https://ce.judge0.com)."""
import base64
import time

import httpx

from app.services.judge.base import JudgeJob, JudgeOutcome, RunStatus, internal_error
from app.services.languages import get_language

BATCH_SIZE = 20  # Judge0's default MAX_SUBMISSION_BATCH_SIZE
RESULT_FIELDS = "token,stdout,stderr,compile_output,message,status_id,time,memory"
# Judge0 status ids: 1 In Queue, 2 Processing, 3 Accepted, 4 Wrong Answer,
# 5 Time Limit Exceeded, 6 Compilation Error, 7-12 Runtime Error, 13 Internal Error, 14 Exec Format Error
PENDING = {1, 2}


def _b64(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def _unb64(value: str | None) -> str:
    if not value:
        return ""
    try:
        return base64.b64decode(value).decode("utf-8", errors="replace")
    except Exception:
        return ""


class Judge0Judge:
    def __init__(
        self,
        base_url: str,
        auth_token: str | None = None,
        auth_header: str = "X-Auth-Token",
        poll_interval: float = 0.5,
        timeout_seconds: float = 60,
        max_cpu_seconds: float = 15,
        max_wall_seconds: float = 20,
        max_memory_kb: int = 512000,
        client: httpx.Client | None = None,
        sleep=time.sleep,
    ):
        headers = {auth_header: auth_token} if auth_token else {}
        self._http = client or httpx.Client(base_url=base_url.rstrip("/"), headers=headers, timeout=15)
        self._poll = poll_interval
        self._max_cpu, self._max_wall, self._max_memory = max_cpu_seconds, max_wall_seconds, max_memory_kb
        self._timeout = timeout_seconds
        self._sleep = sleep

    # ---- public ----
    def run_jobs(self, jobs: list[JudgeJob]) -> list[JudgeOutcome]:
        outcomes: list[JudgeOutcome] = []
        for start in range(0, len(jobs), BATCH_SIZE):
            outcomes.extend(self._run_batch(jobs[start : start + BATCH_SIZE]))
        return outcomes

    # ---- internals ----
    def _payload(self, job: JudgeJob) -> dict | None:
        lang = get_language(job.language)
        if lang is None:
            return None
        # Stay inside what the Judge0 server accepts, or it rejects the whole job.
        cpu_seconds = min(max(0.1, job.time_limit_ms / 1000 * lang.time_multiplier), self._max_cpu)
        wall_seconds = min(cpu_seconds * 3 + 2, self._max_wall)
        memory_kb = min(max(job.memory_limit_mb * 1024, lang.min_memory_kb), self._max_memory)
        return {
            "language_id": lang.judge0_id,
            "source_code": _b64(job.source_code),
            "stdin": _b64(job.stdin),
            "cpu_time_limit": round(cpu_seconds, 3),
            "wall_time_limit": round(wall_seconds, 3),  # catches programs that just sleep
            "memory_limit": memory_kb,
            "max_file_size": 1024,
            "enable_network": False,
            "number_of_runs": 1,
        }

    def _run_batch(self, jobs: list[JudgeJob]) -> list[JudgeOutcome]:
        results: list[JudgeOutcome | None] = [None] * len(jobs)
        payloads: list[tuple[int, dict]] = []
        for i, job in enumerate(jobs):
            payload = self._payload(job)
            if payload is None:
                results[i] = internal_error(f"Language '{job.language}' is not supported.")
            else:
                payloads.append((i, payload))
        if not payloads:
            return results  # type: ignore[return-value]

        try:
            tokens = self._create(payloads)
            token_to_index = {}
            for (i, _), entry in zip(payloads, tokens):
                if isinstance(entry, dict) and entry.get("token"):
                    token_to_index[entry["token"]] = i
                else:
                    results[i] = internal_error(f"Judge rejected the job: {entry}")
            if token_to_index:
                raw = self._wait_for(list(token_to_index))
                for token, i in token_to_index.items():
                    item = raw.get(token)
                    results[i] = self._convert(item) if item else internal_error("The judge lost this job.")
        except _JudgeUnavailable as err:
            for i, _ in payloads:
                if results[i] is None:
                    results[i] = internal_error(str(err))
        return results  # type: ignore[return-value]

    def _create(self, payloads: list[tuple[int, dict]]) -> list:
        body = {"submissions": [p for _, p in payloads]}
        delay = 0.5
        for attempt in range(4):
            try:
                res = self._http.post("/submissions/batch", params={"base64_encoded": "true"}, json=body)
            except httpx.HTTPError:
                raise _JudgeUnavailable("The code judge is not reachable right now. Please try again later.")
            if res.status_code == 503:  # "queue is full": wait a little and try again
                self._sleep(delay)
                delay *= 2
                continue
            if res.status_code in (401, 403):
                raise _JudgeUnavailable("The code judge refused our login. Check JUDGE0_AUTH_TOKEN.")
            if res.status_code not in (200, 201):
                raise _JudgeUnavailable(f"The code judge answered with an error (HTTP {res.status_code}).")
            data = res.json()
            if not isinstance(data, list) or len(data) != len(payloads):
                raise _JudgeUnavailable("The code judge sent an answer we did not expect.")
            return data
        raise _JudgeUnavailable("The code judge is busy. Please try again in a minute.")

    def _wait_for(self, tokens: list[str]) -> dict[str, dict]:
        deadline = time.monotonic() + self._timeout
        while True:
            try:
                res = self._http.get(
                    "/submissions/batch",
                    params={"tokens": ",".join(tokens), "base64_encoded": "true", "fields": RESULT_FIELDS},
                )
            except httpx.HTTPError:
                raise _JudgeUnavailable("Lost contact with the code judge. Please try again.")
            if res.status_code != 200:
                raise _JudgeUnavailable(f"The code judge answered with an error (HTTP {res.status_code}).")
            items = res.json().get("submissions", [])
            by_token = {item.get("token"): item for item in items if item}
            pending = [
                t for t in tokens
                if t not in by_token or _status_id(by_token[t]) in PENDING
            ]
            if not pending:
                return by_token
            if time.monotonic() > deadline:
                raise _JudgeUnavailable("The code judge took too long. Please try again.")
            self._sleep(self._poll)

    @staticmethod
    def _convert(item: dict) -> JudgeOutcome:
        status_id = _status_id(item)
        stdout, stderr = _unb64(item.get("stdout")), _unb64(item.get("stderr"))
        compile_output, message = _unb64(item.get("compile_output")), _unb64(item.get("message"))
        try:
            time_ms = int(round(float(item.get("time") or 0) * 1000))
        except (TypeError, ValueError):
            time_ms = 0
        memory_kb = int(item.get("memory") or 0)
        common = dict(stdout=stdout, stderr=stderr, compile_output=compile_output, message=message,
                      time_ms=time_ms, memory_kb=memory_kb)
        if status_id == 3 or status_id == 4:  # we do not send expected_output, but accept both
            return JudgeOutcome(status=RunStatus.ok, **common)
        if status_id == 5:
            return JudgeOutcome(status=RunStatus.time_limit, **common)
        if status_id == 6:
            return JudgeOutcome(status=RunStatus.compile_error, **common)
        if 7 <= status_id <= 12:
            return JudgeOutcome(status=RunStatus.runtime_error, **common)
        return JudgeOutcome(status=RunStatus.internal_error, **{**common, "message": message or "Internal judge error."})


def _status_id(item: dict) -> int:
    try:
        return int(item.get("status_id") or 0)
    except (TypeError, ValueError):
        return 0


class _JudgeUnavailable(Exception):
    pass
