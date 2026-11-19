from app.core.config import get_settings
from app.services.judge.base import Judge, JudgeJob, JudgeOutcome, RunStatus  # noqa: F401

_judge: Judge | None = None


def get_judge() -> Judge:
    """FastAPI dependency. Builds the judge chosen in .env (JUDGE_BACKEND) once."""
    global _judge
    if _judge is None:
        settings = get_settings()
        if settings.judge_backend == "local":
            from app.services.judge.local import LocalJudge

            _judge = LocalJudge()
        elif settings.judge_backend == "judge0":
            from app.services.judge.judge0 import Judge0Judge

            _judge = Judge0Judge(
                base_url=settings.judge0_url,
                auth_token=settings.judge0_auth_token,
                auth_header=settings.judge0_auth_header,
                poll_interval=settings.judge_poll_interval,
                timeout_seconds=settings.judge_timeout_seconds,
                max_cpu_seconds=settings.judge0_max_cpu_seconds,
                max_wall_seconds=settings.judge0_max_wall_seconds,
                max_memory_kb=settings.judge0_max_memory_kb,
            )
        else:
            raise RuntimeError(f"Unknown JUDGE_BACKEND '{settings.judge_backend}'. Use 'judge0' or 'local'.")
    return _judge
