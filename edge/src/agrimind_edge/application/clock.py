"""Injectable clocks for deterministic wall-clock scheduling."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    def now_utc(self) -> datetime: ...


class SystemUtcClock:
    def now_utc(self) -> datetime:
        return datetime.now(UTC)
