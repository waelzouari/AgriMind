"""Standard-library scheduler adapter for bounded pump runs."""

from __future__ import annotations

from collections.abc import Callable
from threading import Timer


class ThreadingScheduler:
    def schedule(self, delay_seconds: int, callback: Callable[[], None]) -> Timer:
        timer = Timer(delay_seconds, callback)
        timer.daemon = True
        timer.start()
        return timer
