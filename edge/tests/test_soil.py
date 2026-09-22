from __future__ import annotations

from collections.abc import Iterable

import pytest

from agrimind_edge.adapters.hardware.soil import SoilMoistureSensor, soil_moisture_percent
from agrimind_edge.config import HardwareConfig


class ScriptedChannel:
    def __init__(self, values: Iterable[int | Exception]) -> None:
        self._values = iter(values)

    @property
    def value(self) -> int:
        value = next(self._values)
        if isinstance(value, Exception):
            raise value
        return value


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(28_000, 0.0), (11_000, 100.0), (19_500, 50.0), (40_000, 0.0), (1_000, 100.0)],
)
def test_soil_conversion_preserves_calibration_and_clamping(raw: int, expected: float) -> None:
    assert soil_moisture_percent(raw, dry_raw=28_000, wet_raw=11_000) == expected


def test_soil_average_uses_integer_floor_and_50ms_per_sample() -> None:
    sleeps: list[float] = []
    sensor = SoilMoistureSensor(
        lambda: ScriptedChannel([10, 11, 12]),
        HardwareConfig(),
        sleep=sleeps.append,
    )

    assert sensor.read_raw_average(samples=3) == 11
    assert sleeps == [0.05, 0.05, 0.05]


def test_soil_read_returns_error_shape_on_channel_failure() -> None:
    sensor = SoilMoistureSensor(
        lambda: ScriptedChannel([RuntimeError("adc unavailable")]),
        HardwareConfig(),
        sleep=lambda _: None,
    )

    assert sensor.read() == {
        "soil_humidity": None,
        "soil_raw": None,
        "error": "adc unavailable",
    }


def test_soil_rejects_zero_samples() -> None:
    sensor = SoilMoistureSensor(lambda: ScriptedChannel([]), HardwareConfig())

    with pytest.raises(ValueError, match="samples must be at least 1"):
        sensor.read_raw_average(samples=0)
