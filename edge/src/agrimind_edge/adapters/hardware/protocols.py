"""Minimal structural types for dependency-injected hardware libraries."""

from __future__ import annotations

from typing import Protocol


class DHTDevice(Protocol):
    @property
    def temperature(self) -> float | None: ...

    @property
    def humidity(self) -> float | None: ...

    def exit(self) -> None: ...


class AnalogChannel(Protocol):
    @property
    def value(self) -> int: ...


class GPIO(Protocol):
    BCM: int
    OUT: int
    IN: int
    HIGH: int
    LOW: int

    def setmode(self, mode: int) -> None: ...

    def setwarnings(self, enabled: bool) -> None: ...

    def setup(self, channel: int, mode: int, initial: int | None = None) -> None: ...

    def output(self, channel: int, value: int | bool) -> None: ...

    def input(self, channel: int) -> int: ...

    def cleanup(self, channel: list[int]) -> None: ...
