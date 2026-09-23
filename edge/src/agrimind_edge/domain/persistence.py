"""Persistence-neutral records for the local event store and MQTT outbox."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from agrimind_edge.contracts import CommandAcknowledgement, PumpCommand, Telemetry
from agrimind_edge.domain.mqtt import MqttPublication


class EdgeEventType(StrEnum):
    TELEMETRY = "telemetry"
    COMMAND_ACKNOWLEDGEMENT = "command_acknowledgement"


class EnqueueResult(StrEnum):
    CREATED = "created"
    PENDING = "pending"
    BROKER_ACCEPTED = "broker_accepted"
    CLOUD_CONFIRMED = "cloud_confirmed"
    REJECTED = "rejected"
    DELIVERED = "delivered"


@dataclass(frozen=True, slots=True)
class EdgeEvent:
    event_id: UUID
    event_type: EdgeEventType
    farm_id: UUID
    device_id: UUID
    occurred_at: datetime
    payload: str

    def __post_init__(self) -> None:
        for name, value in (
            ("event_id", self.event_id),
            ("farm_id", self.farm_id),
            ("device_id", self.device_id),
        ):
            if value.int == 0:
                raise ValueError(f"{name} must be non-zero")
        _require_utc(self.occurred_at, "occurred_at")
        if not self.payload:
            raise ValueError("event payload must not be empty")

    @classmethod
    def from_telemetry(cls, telemetry: Telemetry) -> EdgeEvent:
        return cls(
            event_id=telemetry.message_id,
            event_type=EdgeEventType.TELEMETRY,
            farm_id=telemetry.farm_id,
            device_id=telemetry.device_id,
            occurred_at=telemetry.recorded_at,
            payload=telemetry.to_json(),
        )

    @classmethod
    def from_acknowledgement(cls, acknowledgement: CommandAcknowledgement) -> EdgeEvent:
        return cls(
            event_id=acknowledgement.acknowledgement_id,
            event_type=EdgeEventType.COMMAND_ACKNOWLEDGEMENT,
            farm_id=acknowledgement.farm_id,
            device_id=acknowledgement.device_id,
            occurred_at=acknowledgement.occurred_at,
            payload=acknowledgement.to_json(),
        )


@dataclass(frozen=True, slots=True)
class OutboxEntry:
    event: EdgeEvent
    publication: MqttPublication
    attempt_count: int
    created_at: datetime

    def __post_init__(self) -> None:
        if self.attempt_count < 0:
            raise ValueError("attempt_count must be non-negative")
        _require_utc(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class PruneResult:
    pending_events: int
    delivered_events: int
    processed_commands: int

    def __post_init__(self) -> None:
        if min(self.pending_events, self.delivered_events, self.processed_commands) < 0:
            raise ValueError("prune counts must be non-negative")


@dataclass(frozen=True, slots=True)
class ProcessedCommandRecord:
    command_id: UUID
    command_fingerprint: str
    acknowledgement: CommandAcknowledgement
    processed_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        if self.command_id.int == 0:
            raise ValueError("command_id must be non-zero")
        if len(self.command_fingerprint) != 64 or any(
            character not in "0123456789abcdef" for character in self.command_fingerprint
        ):
            raise ValueError("command_fingerprint must be a lowercase SHA-256 digest")
        if self.acknowledgement.command_id != self.command_id:
            raise ValueError("processed command acknowledgement must match command_id")
        _require_utc(self.processed_at, "processed_at")
        _require_utc(self.expires_at, "expires_at")

    @classmethod
    def from_command(
        cls,
        command: PumpCommand,
        acknowledgement: CommandAcknowledgement,
        processed_at: datetime,
    ) -> ProcessedCommandRecord:
        from hashlib import sha256

        return cls(
            command_id=command.command_id,
            command_fingerprint=sha256(command.to_json().encode()).hexdigest(),
            acknowledgement=acknowledgement,
            processed_at=processed_at,
            expires_at=command.expires_at,
        )

    def matches(self, command: PumpCommand) -> bool:
        from hashlib import sha256

        return self.command_fingerprint == sha256(command.to_json().encode()).hexdigest()


def _require_utc(value: datetime, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
        raise ValueError(f"{field} must be timezone-aware UTC")
