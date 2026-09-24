"""Hardware-independent domain models."""

from agrimind_edge.domain.broker import BrokerState, FailoverPolicy
from agrimind_edge.domain.mqtt import (
    DeviceRuntimeStatus,
    MqttConnectionState,
    MqttPublication,
    ReceivedMqttMessage,
    TelemetryPublishResult,
)
from agrimind_edge.domain.persistence import (
    EdgeEvent,
    EdgeEventType,
    EnqueueResult,
    OutboxEntry,
    ProcessedCommandRecord,
    PruneResult,
)
from agrimind_edge.domain.pump import AutomaticStopResult, PumpDecisionCode, PumpState
from agrimind_edge.domain.schedules import (
    IrrigationSchedule,
    OccurrenceStatus,
    ScheduleOccurrence,
    ScheduleSummary,
)
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
    "BrokerState",
    "DeviceRuntimeStatus",
    "EdgeEvent",
    "EdgeEventType",
    "EnqueueResult",
    "FailoverPolicy",
    "IrrigationSchedule",
    "Measurement",
    "MqttConnectionState",
    "MqttPublication",
    "OccurrenceStatus",
    "OutboxEntry",
    "ProcessedCommandRecord",
    "PruneResult",
    "PumpDecisionCode",
    "PumpResult",
    "PumpState",
    "ReadingQuality",
    "ReceivedMqttMessage",
    "ScheduleOccurrence",
    "ScheduleSummary",
    "SensorError",
    "SensorErrorCode",
    "SensorSnapshot",
    "SoilReading",
    "TankReading",
    "TelemetryPublishResult",
]
