"""Closed v1 wire enumerations shared by contract models and topics."""

from enum import StrEnum


class TelemetryMetric(StrEnum):
    SOIL_MOISTURE = "soil_moisture"
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    TANK_LEVEL = "tank_level"


class TelemetryQuality(StrEnum):
    VALID = "valid"
    ESTIMATED = "estimated"


class PumpAction(StrEnum):
    ON = "on"
    OFF = "off"


class AcknowledgementStatus(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    COMPLETED = "completed"
    FAILED = "failed"


class DeviceHealth(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAULT = "fault"


class IrrigationOutcome(StrEnum):
    INCREASED = "increased"
    UNCHANGED = "unchanged"
    DECREASED = "decreased"
