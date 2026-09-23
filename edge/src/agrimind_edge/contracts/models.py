"""Strict AgriMind v1 wire models with canonical JSON serialization."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Self
from uuid import UUID

from agrimind_edge.contracts.enums import (
    AcknowledgementStatus,
    DeviceHealth,
    IngestionAcknowledgementStatus,
    IrrigationOutcome,
    PumpAction,
    TelemetryMetric,
    TelemetryQuality,
)
from agrimind_edge.contracts.validation import (
    SCHEMA_VERSION,
    decode_json,
    encode_json,
    enum_value,
    finite_number,
    format_utc_timestamp,
    non_negative_integer,
    parse_utc_timestamp,
    parse_uuid,
    require_exact_fields,
    require_schema_version,
)

MAX_PUMP_DURATION_SECONDS = 600
UNIT_BY_METRIC = {
    TelemetryMetric.SOIL_MOISTURE: "%",
    TelemetryMetric.TEMPERATURE: "°C",
    TelemetryMetric.HUMIDITY: "%",
    TelemetryMetric.TANK_LEVEL: "cm",
}


class JsonContract:
    def to_dict(self) -> dict[str, object]:
        raise NotImplementedError

    def to_json(self) -> str:
        return encode_json(self.to_dict())


@dataclass(frozen=True, slots=True)
class Telemetry(JsonContract):
    message_id: UUID
    farm_id: UUID
    device_id: UUID
    metric: TelemetryMetric
    value: float
    unit: str
    recorded_at: datetime
    quality: TelemetryQuality = TelemetryQuality.VALID
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        require_schema_version(self.schema_version)
        for field, value in (
            ("message_id", self.message_id),
            ("farm_id", self.farm_id),
            ("device_id", self.device_id),
        ):
            if value.int == 0:
                raise ValueError(f"{field} must be non-zero")
        finite_number(self.value, "value")
        format_utc_timestamp(self.recorded_at, "recorded_at")
        if self.unit != UNIT_BY_METRIC[self.metric]:
            raise ValueError(f"unit for {self.metric.value} must be {UNIT_BY_METRIC[self.metric]}")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "message_id": str(self.message_id),
            "farm_id": str(self.farm_id),
            "device_id": str(self.device_id),
            "metric": self.metric.value,
            "value": self.value,
            "unit": self.unit,
            "recorded_at": format_utc_timestamp(self.recorded_at, "recorded_at"),
            "quality": self.quality.value,
        }

    @classmethod
    def from_json(cls, payload: str | bytes) -> Self:
        data = decode_json(payload)
        require_exact_fields(
            data,
            required={
                "schema_version",
                "message_id",
                "farm_id",
                "device_id",
                "metric",
                "value",
                "unit",
                "recorded_at",
                "quality",
            },
        )
        metric = enum_value(TelemetryMetric, data["metric"], "metric")
        if not isinstance(data["unit"], str):
            raise ValueError("unit must be a string")
        return cls(
            schema_version=require_schema_version(data["schema_version"]),
            message_id=parse_uuid(data["message_id"], "message_id"),
            farm_id=parse_uuid(data["farm_id"], "farm_id"),
            device_id=parse_uuid(data["device_id"], "device_id"),
            metric=metric,
            value=finite_number(data["value"], "value"),
            unit=data["unit"],
            recorded_at=parse_utc_timestamp(data["recorded_at"], "recorded_at"),
            quality=enum_value(TelemetryQuality, data["quality"], "quality"),
        )


@dataclass(frozen=True, slots=True)
class IngestionAcknowledgement(JsonContract):
    message_id: UUID
    farm_id: UUID
    device_id: UUID
    event_type: str
    status: IngestionAcknowledgementStatus
    occurred_at: datetime
    reason_code: str | None = None
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        require_schema_version(self.schema_version)
        for field, value in (
            ("message_id", self.message_id),
            ("farm_id", self.farm_id),
            ("device_id", self.device_id),
        ):
            if value.int == 0:
                raise ValueError(f"{field} must be non-zero")
        if self.event_type != "telemetry":
            raise ValueError("event_type must be telemetry")
        format_utc_timestamp(self.occurred_at, "occurred_at")
        if self.status is IngestionAcknowledgementStatus.REJECTED:
            if not self.reason_code:
                raise ValueError("reason_code is required for rejected ingestion acknowledgements")
        elif self.reason_code is not None:
            raise ValueError("reason_code is only valid for rejected ingestion acknowledgements")
        if self.reason_code is not None and (
            len(self.reason_code) > 64
            or not self.reason_code.replace("_", "").isalnum()
            or self.reason_code.lower() != self.reason_code
        ):
            raise ValueError("reason_code must be lowercase snake_case up to 64 characters")

    def to_dict(self) -> dict[str, object]:
        data: dict[str, object] = {
            "schema_version": self.schema_version,
            "message_id": str(self.message_id),
            "farm_id": str(self.farm_id),
            "device_id": str(self.device_id),
            "event_type": self.event_type,
            "status": self.status.value,
            "occurred_at": format_utc_timestamp(self.occurred_at, "occurred_at"),
        }
        if self.reason_code is not None:
            data["reason_code"] = self.reason_code
        return data

    @classmethod
    def from_json(cls, payload: str | bytes) -> Self:
        data = decode_json(payload)
        require_exact_fields(
            data,
            required={
                "schema_version",
                "message_id",
                "farm_id",
                "device_id",
                "event_type",
                "status",
                "occurred_at",
            },
            optional={"reason_code"},
        )
        event_type = data["event_type"]
        reason = data.get("reason_code")
        if not isinstance(event_type, str):
            raise ValueError("event_type must be a string")
        if reason is not None and not isinstance(reason, str):
            raise ValueError("reason_code must be a string")
        return cls(
            schema_version=require_schema_version(data["schema_version"]),
            message_id=parse_uuid(data["message_id"], "message_id"),
            farm_id=parse_uuid(data["farm_id"], "farm_id"),
            device_id=parse_uuid(data["device_id"], "device_id"),
            event_type=event_type,
            status=enum_value(IngestionAcknowledgementStatus, data["status"], "status"),
            occurred_at=parse_utc_timestamp(data["occurred_at"], "occurred_at"),
            reason_code=reason,
        )


@dataclass(frozen=True, slots=True)
class PumpCommand(JsonContract):
    command_id: UUID
    farm_id: UUID
    device_id: UUID
    action: PumpAction
    issued_at: datetime
    expires_at: datetime
    requested_by: UUID
    duration_seconds: int | None = None
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        require_schema_version(self.schema_version)
        for field, value in (
            ("command_id", self.command_id),
            ("farm_id", self.farm_id),
            ("device_id", self.device_id),
            ("requested_by", self.requested_by),
        ):
            if value.int == 0:
                raise ValueError(f"{field} must be non-zero")
        format_utc_timestamp(self.issued_at, "issued_at")
        format_utc_timestamp(self.expires_at, "expires_at")
        if self.expires_at <= self.issued_at:
            raise ValueError("expires_at must be after issued_at")
        if self.action is PumpAction.ON:
            valid_duration = self.duration_seconds is not None and (
                1 <= self.duration_seconds <= MAX_PUMP_DURATION_SECONDS
            )
            if not valid_duration:
                raise ValueError(
                    f"duration_seconds for on must be between 1 and {MAX_PUMP_DURATION_SECONDS}"
                )
        elif self.duration_seconds is not None:
            raise ValueError("duration_seconds must be omitted for off")

    def validate_not_expired(self, now: datetime | None = None) -> None:
        current = now or datetime.now(UTC)
        format_utc_timestamp(current, "now")
        if self.expires_at <= current:
            raise ValueError("command has expired")

    def to_dict(self) -> dict[str, object]:
        data: dict[str, object] = {
            "schema_version": self.schema_version,
            "command_id": str(self.command_id),
            "farm_id": str(self.farm_id),
            "device_id": str(self.device_id),
            "action": self.action.value,
            "issued_at": format_utc_timestamp(self.issued_at, "issued_at"),
            "expires_at": format_utc_timestamp(self.expires_at, "expires_at"),
            "requested_by": str(self.requested_by),
        }
        if self.duration_seconds is not None:
            data["duration_seconds"] = self.duration_seconds
        return data

    @classmethod
    def from_json(cls, payload: str | bytes, *, now: datetime | None = None) -> Self:
        command = cls.from_json_without_expiry_validation(payload)
        command.validate_not_expired(now)
        return command

    @classmethod
    def from_json_without_expiry_validation(cls, payload: str | bytes) -> Self:
        """Deserialize a complete v1 command while deferring expiry policy."""

        data = decode_json(payload)
        require_exact_fields(
            data,
            required={
                "schema_version",
                "command_id",
                "farm_id",
                "device_id",
                "action",
                "issued_at",
                "expires_at",
                "requested_by",
            },
            optional={"duration_seconds"},
        )
        raw_duration = data.get("duration_seconds")
        if raw_duration is not None and type(raw_duration) is not int:
            raise ValueError("duration_seconds must be an integer")
        return cls(
            schema_version=require_schema_version(data["schema_version"]),
            command_id=parse_uuid(data["command_id"], "command_id"),
            farm_id=parse_uuid(data["farm_id"], "farm_id"),
            device_id=parse_uuid(data["device_id"], "device_id"),
            action=enum_value(PumpAction, data["action"], "action"),
            issued_at=parse_utc_timestamp(data["issued_at"], "issued_at"),
            expires_at=parse_utc_timestamp(data["expires_at"], "expires_at"),
            requested_by=parse_uuid(data["requested_by"], "requested_by"),
            duration_seconds=raw_duration,
        )


@dataclass(frozen=True, slots=True)
class CommandAcknowledgement(JsonContract):
    acknowledgement_id: UUID
    command_id: UUID
    farm_id: UUID
    device_id: UUID
    status: AcknowledgementStatus
    occurred_at: datetime
    reason_code: str | None = None
    pump_state: bool | None = None
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        require_schema_version(self.schema_version)
        for field, value in (
            ("acknowledgement_id", self.acknowledgement_id),
            ("command_id", self.command_id),
            ("farm_id", self.farm_id),
            ("device_id", self.device_id),
        ):
            if value.int == 0:
                raise ValueError(f"{field} must be non-zero")
        format_utc_timestamp(self.occurred_at, "occurred_at")
        if self.status in {AcknowledgementStatus.REJECTED, AcknowledgementStatus.FAILED}:
            if not self.reason_code:
                raise ValueError("reason_code is required for rejected or failed acknowledgements")
        elif self.reason_code is not None:
            raise ValueError("reason_code is only valid for rejected or failed acknowledgements")
        if self.reason_code is not None and (
            len(self.reason_code) > 64
            or not self.reason_code.replace("_", "").isalnum()
            or self.reason_code.lower() != self.reason_code
        ):
            raise ValueError("reason_code must be lowercase snake_case up to 64 characters")

    def to_dict(self) -> dict[str, object]:
        data: dict[str, object] = {
            "schema_version": self.schema_version,
            "acknowledgement_id": str(self.acknowledgement_id),
            "command_id": str(self.command_id),
            "farm_id": str(self.farm_id),
            "device_id": str(self.device_id),
            "status": self.status.value,
            "occurred_at": format_utc_timestamp(self.occurred_at, "occurred_at"),
        }
        if self.reason_code is not None:
            data["reason_code"] = self.reason_code
        if self.pump_state is not None:
            data["pump_state"] = self.pump_state
        return data

    @classmethod
    def from_json(cls, payload: str | bytes) -> Self:
        data = decode_json(payload)
        require_exact_fields(
            data,
            required={
                "schema_version",
                "acknowledgement_id",
                "command_id",
                "farm_id",
                "device_id",
                "status",
                "occurred_at",
            },
            optional={"reason_code", "pump_state"},
        )
        reason = data.get("reason_code")
        pump_state = data.get("pump_state")
        if reason is not None and not isinstance(reason, str):
            raise ValueError("reason_code must be a string")
        if pump_state is not None and type(pump_state) is not bool:
            raise ValueError("pump_state must be a boolean")
        return cls(
            schema_version=require_schema_version(data["schema_version"]),
            acknowledgement_id=parse_uuid(data["acknowledgement_id"], "acknowledgement_id"),
            command_id=parse_uuid(data["command_id"], "command_id"),
            farm_id=parse_uuid(data["farm_id"], "farm_id"),
            device_id=parse_uuid(data["device_id"], "device_id"),
            status=enum_value(AcknowledgementStatus, data["status"], "status"),
            occurred_at=parse_utc_timestamp(data["occurred_at"], "occurred_at"),
            reason_code=reason,
            pump_state=pump_state,
        )


@dataclass(frozen=True, slots=True)
class DeviceStatus(JsonContract):
    message_id: UUID
    farm_id: UUID
    device_id: UUID
    online: bool
    pump_state: bool
    health: DeviceHealth
    recorded_at: datetime
    uptime_seconds: int
    firmware_version: str
    errors: tuple[str, ...] = ()
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        require_schema_version(self.schema_version)
        for field, value in (
            ("message_id", self.message_id),
            ("farm_id", self.farm_id),
            ("device_id", self.device_id),
        ):
            if value.int == 0:
                raise ValueError(f"{field} must be non-zero")
        format_utc_timestamp(self.recorded_at, "recorded_at")
        non_negative_integer(self.uptime_seconds, "uptime_seconds")
        if not self.firmware_version or len(self.firmware_version) > 64:
            raise ValueError("firmware_version must contain 1 to 64 characters")
        invalid_error = any(
            not error
            or len(error) > 64
            or not error.replace("_", "").isalnum()
            or error.lower() != error
            for error in self.errors
        )
        if len(self.errors) > 16 or invalid_error:
            raise ValueError("errors must contain up to 16 lowercase snake_case codes")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "message_id": str(self.message_id),
            "farm_id": str(self.farm_id),
            "device_id": str(self.device_id),
            "online": self.online,
            "pump_state": self.pump_state,
            "health": self.health.value,
            "recorded_at": format_utc_timestamp(self.recorded_at, "recorded_at"),
            "uptime_seconds": self.uptime_seconds,
            "firmware_version": self.firmware_version,
            "errors": list(self.errors),
        }

    @classmethod
    def from_json(cls, payload: str | bytes) -> Self:
        data = decode_json(payload)
        require_exact_fields(
            data,
            required={
                "schema_version",
                "message_id",
                "farm_id",
                "device_id",
                "online",
                "pump_state",
                "health",
                "recorded_at",
                "uptime_seconds",
                "firmware_version",
                "errors",
            },
        )
        if type(data["online"]) is not bool or type(data["pump_state"]) is not bool:
            raise ValueError("online and pump_state must be booleans")
        if not isinstance(data["firmware_version"], str):
            raise ValueError("firmware_version must be a string")
        raw_errors = data["errors"]
        if not isinstance(raw_errors, list) or any(
            not isinstance(item, str) for item in raw_errors
        ):
            raise ValueError("errors must be an array of strings")
        return cls(
            schema_version=require_schema_version(data["schema_version"]),
            message_id=parse_uuid(data["message_id"], "message_id"),
            farm_id=parse_uuid(data["farm_id"], "farm_id"),
            device_id=parse_uuid(data["device_id"], "device_id"),
            online=data["online"],
            pump_state=data["pump_state"],
            health=enum_value(DeviceHealth, data["health"], "health"),
            recorded_at=parse_utc_timestamp(data["recorded_at"], "recorded_at"),
            uptime_seconds=non_negative_integer(data["uptime_seconds"], "uptime_seconds"),
            firmware_version=data["firmware_version"],
            errors=tuple(raw_errors),
        )


@dataclass(frozen=True, slots=True)
class IrrigationResult(JsonContract):
    event_id: UUID
    farm_id: UUID
    device_id: UUID
    soil_moisture_before: float
    soil_moisture_after: float
    delta: float
    result: IrrigationOutcome
    completed_at: datetime
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        require_schema_version(self.schema_version)
        for field, value in (
            ("event_id", self.event_id),
            ("farm_id", self.farm_id),
            ("device_id", self.device_id),
        ):
            if value.int == 0:
                raise ValueError(f"{field} must be non-zero")
        before = finite_number(self.soil_moisture_before, "soil_moisture_before")
        after = finite_number(self.soil_moisture_after, "soil_moisture_after")
        delta = finite_number(self.delta, "delta")
        if not 0 <= before <= 100 or not 0 <= after <= 100:
            raise ValueError("soil moisture values must be between 0 and 100")
        expected_delta = round(after - before, 1)
        if abs(delta - expected_delta) > 0.001:
            raise ValueError("delta must equal soil_moisture_after - soil_moisture_before")
        expected_result = (
            IrrigationOutcome.INCREASED
            if delta > 0
            else IrrigationOutcome.DECREASED
            if delta < 0
            else IrrigationOutcome.UNCHANGED
        )
        if self.result is not expected_result:
            raise ValueError(f"result must be {expected_result.value} for delta {delta}")
        format_utc_timestamp(self.completed_at, "completed_at")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "event_id": str(self.event_id),
            "farm_id": str(self.farm_id),
            "device_id": str(self.device_id),
            "soil_moisture_before": self.soil_moisture_before,
            "soil_moisture_after": self.soil_moisture_after,
            "delta": self.delta,
            "result": self.result.value,
            "completed_at": format_utc_timestamp(self.completed_at, "completed_at"),
        }

    @classmethod
    def from_json(cls, payload: str | bytes) -> Self:
        data = decode_json(payload)
        require_exact_fields(
            data,
            required={
                "schema_version",
                "event_id",
                "farm_id",
                "device_id",
                "soil_moisture_before",
                "soil_moisture_after",
                "delta",
                "result",
                "completed_at",
            },
        )
        return cls(
            schema_version=require_schema_version(data["schema_version"]),
            event_id=parse_uuid(data["event_id"], "event_id"),
            farm_id=parse_uuid(data["farm_id"], "farm_id"),
            device_id=parse_uuid(data["device_id"], "device_id"),
            soil_moisture_before=finite_number(
                data["soil_moisture_before"], "soil_moisture_before"
            ),
            soil_moisture_after=finite_number(
                data["soil_moisture_after"], "soil_moisture_after"
            ),
            delta=finite_number(data["delta"], "delta"),
            result=enum_value(IrrigationOutcome, data["result"], "result"),
            completed_at=parse_utc_timestamp(data["completed_at"], "completed_at"),
        )
