"""Hardware-independent domain models."""

from agrimind_edge.domain.sensors import (
    AirReading,
    Measurement,
    PumpResult,
    ReadingQuality,
    SensorError,
    SensorErrorCode,
    SensorSnapshot,
    SoilReading,
    TankReading,
)

__all__ = [
    "AirReading",
    "Measurement",
    "PumpResult",
    "ReadingQuality",
    "SensorError",
    "SensorErrorCode",
    "SensorSnapshot",
    "SoilReading",
    "TankReading",
]
