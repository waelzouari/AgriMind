from __future__ import annotations

from collections.abc import Iterable


class FakeGPIO:
    BCM = 11
    OUT = 0
    IN = 1
    HIGH = 1
    LOW = 0

    def __init__(self, inputs: Iterable[int] = ()) -> None:
        self.inputs = iter(inputs)
        self.mode: int | None = None
        self.warnings: bool | None = None
        self.setups: list[tuple[int, int, int | None]] = []
        self.outputs: list[tuple[int, int | bool]] = []
        self.cleaned: list[list[int]] = []

    def setmode(self, mode: int) -> None:
        self.mode = mode

    def setwarnings(self, enabled: bool) -> None:
        self.warnings = enabled

    def setup(self, channel: int, mode: int, initial: int | None = None) -> None:
        self.setups.append((channel, mode, initial))

    def output(self, channel: int, value: int | bool) -> None:
        self.outputs.append((channel, value))

    def input(self, channel: int) -> int:
        del channel
        return next(self.inputs)

    def cleanup(self, channel: list[int]) -> None:
        self.cleaned.append(channel)


class FailingCleanupGPIO(FakeGPIO):
    def cleanup(self, channel: list[int]) -> None:
        del channel
        raise RuntimeError("cleanup failure")
