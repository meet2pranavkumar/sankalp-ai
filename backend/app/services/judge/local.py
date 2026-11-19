"""Runs student code directly on THIS computer.

!!! NOT SAFE. There is NO sandbox here. A student program can read your files,
use the network and do anything you can do. It exists only so you can develop
on a laptop where Judge0 cannot run (for example Docker Desktop on Windows).
It refuses to start unless APP_ENV=development. Never use it for real students.
"""
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from app.core.config import get_settings
from app.services.judge.base import JudgeJob, JudgeOutcome, RunStatus, internal_error
from app.services.languages import get_language

log = logging.getLogger(__name__)

IS_WINDOWS = os.name == "nt"
COMPILE_TIMEOUT_SECONDS = 30
MAX_OUTPUT_BYTES = 1024 * 1024  # 1 MB written to stdout or stderr
READ_LIMIT = 256 * 1024  # how much output we keep and show


class LocalJudge:
    def __init__(self) -> None:
        if get_settings().app_env != "development":
            raise RuntimeError(
                "The local judge is not safe and only works when APP_ENV=development. "
                "Use JUDGE_BACKEND=judge0 for real use."
            )
        log.warning("LOCAL JUDGE ACTIVE: student code runs on this computer with no sandbox.")

    def run_jobs(self, jobs: list[JudgeJob]) -> list[JudgeOutcome]:
        outcomes = []
        for job in jobs:
            try:
                outcomes.append(self._run(job))
            except Exception as err:  # never crash the whole submission because of one job
                log.exception("local judge failed")
                outcomes.append(internal_error(f"Local judge problem: {err}"))
        return outcomes

    # ---- one job ----
    def _run(self, job: JudgeJob) -> JudgeOutcome:
        lang = get_language(job.language)
        if lang is None:
            return internal_error(f"Language '{job.language}' is not supported.")

        with tempfile.TemporaryDirectory(prefix="sankalp-") as tmp:
            work = Path(tmp)
            (work / lang.filename).write_text(job.source_code, encoding="utf-8")

            compile_cmd, run_cmd, missing = self._commands(job, lang.filename, work)
            if missing:
                return internal_error(f"{missing} is not installed on this computer, so {lang.label} cannot run here.")

            if compile_cmd:
                try:
                    done = subprocess.run(
                        compile_cmd, cwd=work, capture_output=True, text=True,
                        timeout=COMPILE_TIMEOUT_SECONDS, errors="replace",
                    )
                except subprocess.TimeoutExpired:
                    return JudgeOutcome(status=RunStatus.compile_error, compile_output="Compilation took too long.")
                if done.returncode != 0:
                    output = (done.stderr or done.stdout or "Compilation failed.")[:READ_LIMIT]
                    return JudgeOutcome(status=RunStatus.compile_error, compile_output=output)

            return self._execute(job, lang.time_multiplier, run_cmd, work)

    def _commands(self, job: JudgeJob, filename: str, work: Path):
        """Returns (compile command or None, run command, name of a missing tool or None)."""
        exe = "prog.exe" if IS_WINDOWS else "prog"
        if job.language == "python":
            return None, [sys.executable, filename], None
        if job.language == "c":
            gcc = shutil.which("gcc")
            return ([gcc, "-O2", "-o", exe, filename, "-lm"], [str(work / exe)], None) if gcc else (None, [], "gcc")
        if job.language == "cpp":
            gpp = shutil.which("g++")
            return ([gpp, "-O2", "-std=c++17", "-o", exe, filename], [str(work / exe)], None) if gpp else (None, [], "g++")
        if job.language == "java":
            javac, java = shutil.which("javac"), shutil.which("java")
            if not javac:
                return None, [], "javac (JDK)"
            if not java:
                return None, [], "java"
            heap = max(64, job.memory_limit_mb)
            return [javac, filename], [java, f"-Xmx{heap}m", "-XX:+UseSerialGC", "-cp", str(work), "Main"], None
        return None, [], job.language

    def _execute(self, job: JudgeJob, multiplier: float, cmd: list[str], work: Path) -> JudgeOutcome:
        limit_s = max(0.1, job.time_limit_ms / 1000 * multiplier)
        (work / "stdin.txt").write_text(job.stdin, encoding="utf-8")
        out_path, err_path = work / "stdout.txt", work / "stderr.txt"
        env = {"PATH": os.environ.get("PATH", ""), "HOME": str(work), "TMPDIR": str(work)}
        if IS_WINDOWS:
            env["SYSTEMROOT"] = os.environ.get("SYSTEMROOT", "")

        started = time.perf_counter()
        timed_out = False
        with open(work / "stdin.txt", "rb") as fin, open(out_path, "wb") as fout, open(err_path, "wb") as ferr:
            proc = subprocess.Popen(
                cmd, cwd=work, stdin=fin, stdout=fout, stderr=ferr, env=env,
                preexec_fn=None if IS_WINDOWS else _limits(job, limit_s),
                start_new_session=not IS_WINDOWS,
            )
            try:
                proc.wait(timeout=limit_s)
            except subprocess.TimeoutExpired:
                timed_out = True
                _kill(proc)
        elapsed_ms = int((time.perf_counter() - started) * 1000)

        stdout = out_path.read_bytes()[:READ_LIMIT].decode("utf-8", errors="replace")
        stderr = err_path.read_bytes()[:READ_LIMIT].decode("utf-8", errors="replace")
        common = dict(stdout=stdout, stderr=stderr, time_ms=elapsed_ms)

        if timed_out:
            return JudgeOutcome(status=RunStatus.time_limit, message="Time limit exceeded", **common)
        if proc.returncode != 0:
            code = proc.returncode
            message = f"Program stopped by signal {-code}" if code < 0 else f"Program exited with code {code}"
            return JudgeOutcome(status=RunStatus.runtime_error, message=message, **common)
        return JudgeOutcome(status=RunStatus.ok, **common)


def _kill(proc: subprocess.Popen) -> None:
    try:
        if IS_WINDOWS:
            proc.kill()
        else:
            import signal

            os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    proc.wait()


def _limits(job: JudgeJob, limit_s: float):
    """Resource limits for the child process (Linux and Mac only)."""
    import resource

    def apply() -> None:
        resource.setrlimit(resource.RLIMIT_CPU, (int(limit_s) + 1, int(limit_s) + 2))
        resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_OUTPUT_BYTES, MAX_OUTPUT_BYTES))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        if job.language != "java":  # the JVM reserves huge address space, so it is limited with -Xmx instead
            mem = max(job.memory_limit_mb, 256) * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (mem, mem))

    return apply
