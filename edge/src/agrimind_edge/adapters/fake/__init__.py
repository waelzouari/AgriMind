"""Deterministic hardware fakes for development and automated tests."""

from agrimind_edge.adapters.fake.hardware import (
    FakeAirSensor,
    FakePump,
    FakeSoilSensor,
    FakeTankSensor,
)

__all__ = ["FakeAirSensor", "FakePump", "FakeSoilSensor", "FakeTankSensor"]
