"""Time helpers (single place so tests can patch them)."""
from __future__ import annotations

from datetime import datetime, timezone

FMT = "%Y-%m-%d %H:%M:%S"


def now() -> datetime:
    return datetime.now(timezone.utc)


def ts(dt: datetime | None = None) -> str:
    return (dt or now()).strftime(FMT)
