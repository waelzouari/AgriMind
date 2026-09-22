"""Deterministic hardware fakes for development and automated tests."""

from agrimind_edge.adapters.fake.hardware import (
    FakeAirSensor,
    FakePump,
    FakeSoilSensor,
    FakeTankSensor,
)
from agrimind_edge.adapters.fake.scheduling import FakeScheduledCall, FakeScheduler

__all__ = [
    "FakeAirSensor",
    "FakePump",
    "FakeScheduledCall",
    "FakeScheduler",
    "FakeSoilSensor",
    "FakeTankSensor",
]
