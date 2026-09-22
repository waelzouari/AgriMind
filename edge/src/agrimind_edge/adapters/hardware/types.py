"""Backward-compatible names for hardware adapter result types."""

from agrimind_edge.domain.sensors import (
    AirReading as DHT22Reading,
)
from agrimind_edge.domain.sensors import (
    PumpResult,
    SoilReading,
    TankReading,
)

__all__ = ["DHT22Reading", "PumpResult", "SoilReading", "TankReading"]
