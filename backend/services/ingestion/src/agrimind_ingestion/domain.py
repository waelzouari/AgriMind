"""Backend-only values for registry and ingestion outcomes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


class MessageKind(StrEnum):
    TELEMETRY = "telemetry"
    DEVICE_STATUS = "device_status"
    COMMAND_ACKNOWLEDGEMENT = "command_acknowledgement"
    IRRIGATION_RESULT = "irrigation_result"


class IngestionOutcome(StrEnum):
    INSERTED = "inserted"
    DUPLICATE = "duplicate"
    REJECTED = "rejected"
    RETRYABLE = "retryable"


class RegistrationOutcome(StrEnum):
    CREATED = "created"
    EXISTING = "existing"
    UPDATED = "updated"


@dataclass(frozen=True, slots=True)
class DeviceRegistration:
    device_id: UUID
    farm_id: UUID
    label: str | None
    is_active: bool


@dataclass(frozen=True, slots=True)
class TopicIdentity:
    kind: MessageKind
    farm_id: UUID
    device_id: UUID
    metric: str | None = None
    command_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class ValidatedMessage:
    identity: TopicIdentity
    message_id: UUID
    recorded_at: datetime
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class IngestionResult:
    outcome: IngestionOutcome
    reason_code: str
    message_id: UUID | None = None
    device_id: UUID | None = None
    farm_id: UUID | None = None
    message_kind: MessageKind | None = None

    @property
    def terminal(self) -> bool:
        return self.outcome is not IngestionOutcome.RETRYABLE

    @property
    def correlatable_event(self) -> bool:
        return (
            self.message_kind
            in {
                MessageKind.TELEMETRY,
                MessageKind.COMMAND_ACKNOWLEDGEMENT,
                MessageKind.IRRIGATION_RESULT,
            }
            and self.message_id is not None
            and self.farm_id is not None
            and self.device_id is not None
        )

    @property
    def correlatable_telemetry(self) -> bool:
        """Backward-compatible telemetry-only correlation predicate."""

        return self.message_kind is MessageKind.TELEMETRY and self.correlatable_event


@dataclass(frozen=True, slots=True)
class RegistrationResult:
    outcome: RegistrationOutcome
    registration: DeviceRegistration


class PersistenceUnavailable(RuntimeError):
    """A transient trusted persistence failure."""


class PersistenceRejected(RuntimeError):
    """A permanent rejection returned by the trusted database boundary."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


class RegistryConflict(RuntimeError):
    """The stable device identity is already bound to another farm."""
