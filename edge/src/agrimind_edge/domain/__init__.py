"""Hardware-independent domain models."""

from agrimind_edge.domain.mqtt import (
    DeviceRuntimeStatus,
    MqttConnectionState,
    MqttPublication,
    ReceivedMqttMessage,
    TelemetryPublishResult,
)
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
    "DeviceRuntimeStatus",
    "Measurement",
    "MqttConnectionState",
    "MqttPublication",
    "PumpDecisionCode",
    "PumpResult",
    "PumpState",
    "ReadingQuality",
    "ReceivedMqttMessage",
    "SensorError",
    "SensorErrorCode",
    "SensorSnapshot",
    "SoilReading",
    "TankReading",
    "TelemetryPublishResult",
]
