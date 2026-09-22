from __future__ import annotations

import sys

import pytest

from agrimind_edge.adapters.fake import (
    FakeAirSensor,
    FakePump,
    FakeSoilSensor,
    FakeTankSensor,
)
from agrimind_edge.adapters.hardware import (
    DHT22Sensor,
    PumpRelay,
    SoilMoistureSensor,
    UltrasonicTankSensor,
)
from agrimind_edge.application import (
    AirSensorPort,
    PumpPort,
    SoilSensorPort,
    TankSensorPort,
)
from agrimind_edge.config import HardwareConfig


class NoOpGPIO:
    BCM = 11
    OUT = 0
    IN = 1
    HIGH = 1
    LOW = 0

    def setmode(self, mode: int) -> None:
        del mode

    def setwarnings(self, enabled: bool) -> None:
        del enabled

    def setup(self, channel: int, mode: int, initial: int | None = None) -> None:
        del channel, mode, initial

    def output(self, channel: int, value: int | bool) -> None:
        del channel, value

    def input(self, channel: int) -> int:
        del channel
        return 0

    def cleanup(self, channel: list[int]) -> None:
        del channel


def test_real_adapters_match_capability_protocols_without_hardware_access() -> None:
    config = HardwareConfig()
    gpio = NoOpGPIO()

    assert isinstance(DHT22Sensor(lambda: pytest.fail("must remain lazy")), AirSensorPort)
    assert isinstance(
        SoilMoistureSensor(lambda: pytest.fail("must remain lazy"), config), SoilSensorPort
    )
    assert isinstance(UltrasonicTankSensor(gpio, config), TankSensorPort)
    assert isinstance(PumpRelay(gpio, config), PumpPort)
    assert "RPi.GPIO" not in sys.modules
    assert "adafruit_dht" not in sys.modules


def test_fake_adapters_match_protocols_and_are_deterministic() -> None:
    air = FakeAirSensor(
        [
            {"temperature": 20.0, "humidity_air": 50.0, "error": None},
            RuntimeError("scripted"),
        ]
    )
    soil = FakeSoilSensor([{"soil_humidity": 40.0, "soil_raw": 21_000, "error": None}])
    tank = FakeTankSensor(
        [{"distance_cm": 5.0, "water_level_cm": 23.0, "water_pct": 76.7, "error": None}]
    )
    pump = FakePump()

    assert isinstance(air, AirSensorPort)
    assert isinstance(soil, SoilSensorPort)
    assert isinstance(tank, TankSensorPort)
    assert isinstance(pump, PumpPort)
    assert air.read()["temperature"] == 20.0
    with pytest.raises(RuntimeError, match="scripted"):
        air.read()
    assert air.read_count == 2
    with pytest.raises(RuntimeError, match="exhausted"):
        air.read()
    assert air.read_count == 3


def test_fake_pump_has_only_raw_deterministic_relay_behavior() -> None:
    pump = FakePump()

    assert pump.get_state() is False
    assert pump.turn_on()["pump"] is True
    assert pump.get_state() is True
    assert pump.turn_off()["pump"] is False
    pump.cleanup()

    assert pump.get_state() is False
    assert pump.calls == ["initialize", "turn_on", "turn_off", "cleanup"]


def test_empty_fake_script_is_rejected() -> None:
    with pytest.raises(ValueError, match="at least one"):
        FakeAirSensor([])
