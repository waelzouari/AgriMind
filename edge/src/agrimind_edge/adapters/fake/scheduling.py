"""Deterministic scheduler used by pump state-machine tests."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(slots=True)
class FakeScheduledCall:
    delay_seconds: int
    callback: Callable[[], None]
    cancelled: bool = False
    fired: bool = False

    def cancel(self) -> None:
        self.cancelled = True

    def fire(self) -> None:
        if not self.cancelled and not self.fired:
            self.fired = True
            self.callback()


class FakeScheduler:
    def __init__(self, *, failure: Exception | None = None) -> None:
        self.calls: list[FakeScheduledCall] = []
        self._failure = failure

    def schedule(self, delay_seconds: int, callback: Callable[[], None]) -> FakeScheduledCall:
        if self._failure is not None:
            raise self._failure
        call = FakeScheduledCall(delay_seconds, callback)
        self.calls.append(call)
        return call

    def fire_next(self) -> None:
        for call in self.calls:
            if not call.cancelled and not call.fired:
                call.fire()
                return
        raise RuntimeError("no pending fake scheduled call")
