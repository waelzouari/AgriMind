"""Application services and hardware-independent ports."""

from agrimind_edge.application.automatic_irrigation import (
    AutomaticIrrigationService,
    IndependentAutomaticSafetyGate,
)
from agrimind_edge.application.inference_ports import IrrigationModelPort
from agrimind_edge.application.ingestion_acknowledgements import (
    IngestionAcknowledgementProcessor,
)
from agrimind_edge.application.irrigation_inference import IrrigationInferenceService
from agrimind_edge.application.mqtt_acl import DeviceAclPolicy
from agrimind_edge.application.mqtt_commands import (
    MqttAcknowledgementPublisher,
    MqttPumpCommandProcessor,
)
from agrimind_edge.application.mqtt_failover import FailoverEventPublisher, FailoverMqttTransport
from agrimind_edge.application.mqtt_service import CloudMqttService
from agrimind_edge.application.outbox_service import OutboxService
from agrimind_edge.application.ports import (
    AirSensorPort,
    PumpPort,
    SoilSensorPort,
    TankSensorPort,
)
from agrimind_edge.application.pump_command_handler import PumpCommandHandler
from agrimind_edge.application.pump_controller import SafePumpController
from agrimind_edge.application.scheduled_irrigation import (
    ScheduledIrrigationRunner,
    ScheduledIrrigationService,
)
from agrimind_edge.application.sensor_service import SensorService
from agrimind_edge.application.telemetry import TelemetryMapper

__all__ = [
    "AirSensorPort",
    "AutomaticIrrigationService",
    "CloudMqttService",
    "DeviceAclPolicy",
    "FailoverEventPublisher",
    "FailoverMqttTransport",
    "IndependentAutomaticSafetyGate",
    "IngestionAcknowledgementProcessor",
    "IrrigationInferenceService",
    "IrrigationModelPort",
    "MqttAcknowledgementPublisher",
    "MqttPumpCommandProcessor",
    "OutboxService",
    "PumpCommandHandler",
    "PumpPort",
    "SafePumpController",
    "ScheduledIrrigationRunner",
    "ScheduledIrrigationService",
    "SensorService",
    "SoilSensorPort",
    "TankSensorPort",
    "TelemetryMapper",
]
