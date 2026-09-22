"""Scripted, deterministic implementations of edge hardware ports."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Mapping
from typing import Generic, TypeVar

from agrimind_edge.domain.sensors import AirReading, PumpResult, SoilReading, TankReading

T = TypeVar("T")


class _Script(Generic[T]):
    def __init__(self, steps: Iterable[T | Exception]) -> None:
        self._steps = deque(steps)
        if not self._steps:
            raise ValueError("fake hardware script must contain at least one step")
        self.read_count = 0

    def next(self) -> T:
        self.read_count += 1
        if not self._steps:
            raise RuntimeError("fake hardware script exhausted")
        step = self._steps.popleft()
        if isinstance(step, Exception):
            raise step
        return step


class FakeAirSensor:
    def __init__(self, steps: Iterable[AirReading | Exception]) -> None:
        self._script = _Script(steps)

    @property
    def read_count(self) -> int:
        return self._script.read_count

    def read(self, retries: int = 3) -> AirReading:
        del retries
        return self._script.next()


class FakeSoilSensor:
    def __init__(self, steps: Iterable[SoilReading | Exception]) -> None:
        self._script = _Script(steps)

    @property
    def read_count(self) -> int:
        return self._script.read_count

    def read(self) -> SoilReading:
        return self._script.next()


class FakeTankSensor:
    def __init__(self, steps: Iterable[TankReading | Exception]) -> None:
        self._script = _Script(steps)

    @property
    def read_count(self) -> int:
        return self._script.read_count

    def read(self) -> TankReading:
        return self._script.next()


class FakePump:
    """In-memory raw relay fake; it deliberately has no safety policy."""

    def __init__(
        self,
        failures: Mapping[str, Iterable[Exception]] | None = None,
    ) -> None:
        self.initialized = False
        self.active = False
        self.calls: list[str] = []
        self._failures = {
            operation: deque(exceptions) for operation, exceptions in (failures or {}).items()
        }

    def _maybe_fail(self, operation: str) -> None:
        failures = self._failures.get(operation)
        if failures:
            raise failures.popleft()

    def initialize(self) -> None:
        self.calls.append("initialize")
        self._maybe_fail("initialize")
        self.initialized = True
        self.active = False

    def get_state(self) -> bool:
        self._maybe_fail("get_state")
        return self.active

    def turn_on(self) -> PumpResult:
        if not self.initialized:
            self.initialize()
        self.calls.append("turn_on")
        self._maybe_fail("turn_on")
        self.active = True
        return {"pump": True, "message": "fake pump on"}

    def turn_off(self) -> PumpResult:
        if not self.initialized:
            self.initialize()
        self.calls.append("turn_off")
        self._maybe_fail("turn_off")
        self.active = False
        return {"pump": False, "message": "fake pump off"}

    def cleanup(self) -> None:
        self.calls.append("cleanup")
        self._maybe_fail("cleanup")
        self.active = False
        self.initialized = False
