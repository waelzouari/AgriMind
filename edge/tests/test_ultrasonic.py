from collections.abc import Iterable

import pytest

from agrimind_edge.adapters.hardware.ultrasonic import (
    UltrasonicTankSensor,
    tank_level_from_distance,
)
from agrimind_edge.config import HardwareConfig
from tests.fakes import FakeGPIO


class ScriptedClock:
    def __init__(self, values: Iterable[float]) -> None:
        self._values = iter(values)

    def __call__(self) -> float:
        return next(self._values)


def test_tank_conversion_preserves_height_offset_and_clamping() -> None:
    assert tank_level_from_distance(8.0, tank_height_cm=30.0, tank_offset_cm=2.0) == (
        20.0,
        66.7,
    )
    assert tank_level_from_distance(40.0, tank_height_cm=30.0, tank_offset_cm=2.0) == (
        0.0,
        0.0,
    )


def test_ultrasonic_pulse_timing_and_distance() -> None:
    gpio = FakeGPIO(inputs=[0, 1, 1, 0])
    sleeps: list[float] = []
    sensor = UltrasonicTankSensor(
        gpio,
        HardwareConfig(),
        sleep=sleeps.append,
        clock=ScriptedClock([0.0, 0.001, 0.0015, 0.002]),
    )

    assert sensor.measure_distance() == 17.15
    assert sleeps == [0.0002, 0.00001]
    assert gpio.outputs == [(23, False), (23, True), (23, False)]


def test_ultrasonic_timeout_returns_prototype_error_result() -> None:
    gpio = FakeGPIO(inputs=[0])
    sensor = UltrasonicTankSensor(
        gpio,
        HardwareConfig(),
        sleep=lambda _: None,
        clock=ScriptedClock([0.0, 1.1]),
    )

    assert sensor.read() == {
        "distance_cm": -1,
        "water_level_cm": 0,
        "water_pct": 0,
        "error": "Capteur non détecté",
    }


def test_ultrasonic_cleanup_releases_only_its_pins() -> None:
    gpio = FakeGPIO()
    sensor = UltrasonicTankSensor(gpio, HardwareConfig())
    sensor.initialize()

    sensor.cleanup()

    assert gpio.cleaned == [[23, 24]]


def test_tank_config_rejects_invalid_geometry() -> None:
    with pytest.raises(ValueError, match="less than tank height"):
        HardwareConfig(tank_height_cm=10, tank_offset_cm=10)
