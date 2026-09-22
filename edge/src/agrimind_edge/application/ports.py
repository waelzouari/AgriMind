"""Small capability ports implemented by real and fake hardware adapters."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, runtime_checkable

from agrimind_edge.domain.sensors import AirReading, PumpResult, SoilReading, TankReading


@runtime_checkable
class AirSensorPort(Protocol):
    def read(self, retries: int = 3) -> AirReading: ...


@runtime_checkable
class SoilSensorPort(Protocol):
    def read(self) -> SoilReading: ...


@runtime_checkable
class TankSensorPort(Protocol):
    def read(self) -> TankReading: ...


@runtime_checkable
class PumpPort(Protocol):
    """Raw relay capability only; safety orchestration belongs to AGM-005."""

    def initialize(self) -> None: ...

    def get_state(self) -> bool: ...

    def turn_on(self) -> PumpResult: ...

    def turn_off(self) -> PumpResult: ...

    def cleanup(self) -> None: ...


class ScheduledCall(Protocol):
    def cancel(self) -> None: ...


class SchedulerPort(Protocol):
    """Schedule a deferred callback without exposing a concrete timer."""

    def schedule(self, delay_seconds: int, callback: Callable[[], None]) -> ScheduledCall: ...
