from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App settings. Values come from environment variables or the .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Sankalp AI"
    app_env: str = "development"
    database_url: str = "sqlite:///./sankalp.db"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    secret_key: str = "dev-only-secret-change-me"
    access_token_expire_minutes: int = 480
    bcrypt_rounds: int = 12  # higher = safer but slower. Tests use 4.

    # --- code judge ---
    # "judge0": real sandbox (use this in production)
    # "local":  runs code on THIS computer without a sandbox. Development only.
    judge_backend: str = "judge0"
    judge0_url: str = "http://localhost:2358"
    judge0_auth_token: str | None = None
    judge0_auth_header: str = "X-Auth-Token"
    # Judge0 refuses jobs above its own maximums. These must match judge0.conf
    # (MAX_CPU_TIME_LIMIT, MAX_WALL_TIME_LIMIT, MAX_MEMORY_LIMIT). See deploy/judge0/README.md.
    judge0_max_cpu_seconds: float = 15
    judge0_max_wall_seconds: float = 20
    judge0_max_memory_kb: int = 512000
    judge_poll_interval: float = 0.5  # seconds between result checks
    judge_timeout_seconds: float = 60  # give up waiting for the judge after this
    submit_cooldown_seconds: float = 5  # minimum gap between two submits by one user
    run_cooldown_seconds: float = 2
    max_source_bytes: int = 65536

    # --- AI helper ---
    # "none": switched off (the helper says it is not set up). "demo": fixed example hints, no AI, for trying the screens.
    # "anthropic": the Claude API. Needs ANTHROPIC_API_KEY.
    ai_provider: str = "none"
    anthropic_api_key: str | None = None
    ai_model: str = "claude-haiku-5-5"  # a small, cheap model is enough for hints. Check the name in your Anthropic console.
    ai_base_url: str = "https://api.anthropic.com"
    ai_max_output_tokens: int = 400
    ai_timeout_seconds: float = 30
    ai_hints_per_problem_per_day: int = 5  # counted over the last 24 hours
    ai_explains_per_problem_per_day: int = 10
    ai_hint_cooldown_seconds: float = 60  # a student must wait a little between hints for the same problem
    ai_user_daily_cap: int = 40  # all problems together, so one student cannot run up the bill

    # --- reports ---
    # "Today" and "streak" are counted in the college's own time zone, as minutes after UTC. 330 = India (UTC+5:30).
    report_utc_offset_minutes: int = 330

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
