"""The one place that knows what time it is. Tests replace utc_now() to travel in time."""
from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def aware(moment: datetime) -> datetime:
    """SQLite gives back dates without a time zone. All our dates are UTC, so add it."""
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)
