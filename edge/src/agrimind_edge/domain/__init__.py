"""Hardware-independent domain models."""

from agrimind_edge.domain.pump import AutomaticStopResult, PumpDecisionCode, PumpState
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
    "AutomaticStopResult",
    "Measurement",
    "PumpDecisionCode",
    "PumpResult",
    "PumpState",
    "ReadingQuality",
    "SensorError",
    "SensorErrorCode",
    "SensorSnapshot",
    "SoilReading",
    "TankReading",
]
