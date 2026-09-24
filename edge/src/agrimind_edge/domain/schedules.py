"""Domain records for one-shot local scheduled irrigation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid5

from agrimind_edge.contracts.models import MAX_PUMP_DURATION_SECONDS
from agrimind_edge.contracts.validation import format_utc_timestamp

OCCURRENCE_NAMESPACE = UUID("ed769e8c-d999-58aa-8970-568c55d9d7bf")
COMMAND_NAMESPACE = UUID("13633b79-aa35-5260-a29e-65cc96c894f8")
SCHEDULER_IDENTITY_NAMESPACE = UUID("c7b30ce2-1daf-56a2-a088-6f9f364a39d1")


class OccurrenceStatus(StrEnum):
    CLAIMED = "claimed"
    COMMAND_ACCEPTED = "command_accepted"
    REJECTED = "rejected"
    MISSED = "missed"
    FAILED = "failed"
    UNKNOWN_AFTER_ACCEPTANCE = "unknown_after_acceptance"
    UNKNOWN_AFTER_RESTART = "unknown_after_restart"

    @property
    def terminal(self) -> bool:
        return self is not OccurrenceStatus.CLAIMED


def require_utc(value: datetime, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
        raise ValueError(f"{field} must be timezone-aware UTC")
    return value


def occurrence_id_for(schedule_id: UUID, scheduled_for: datetime) -> UUID:
    instant = format_utc_timestamp(require_utc(scheduled_for, "scheduled_for"), "scheduled_for")
    return uuid5(OCCURRENCE_NAMESPACE, f"{schedule_id}:{instant}")


def command_id_for(occurrence_id: UUID) -> UUID:
    return uuid5(COMMAND_NAMESPACE, f"{occurrence_id}:pump-on")


def scheduler_requested_by(farm_id: UUID, device_id: UUID) -> UUID:
    return uuid5(SCHEDULER_IDENTITY_NAMESPACE, f"{farm_id}:{device_id}:local_scheduler")


@dataclass(frozen=True, slots=True)
class IrrigationSchedule:
    schedule_id: UUID
    farm_id: UUID
    device_id: UUID
    scheduled_for: datetime
    duration_seconds: int
    enabled: bool
    created_at: datetime
    updated_at: datetime
    disabled_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.schedule_id.int == 0 or self.farm_id.int == 0 or self.device_id.int == 0:
            raise ValueError("schedule, farm, and device IDs must be non-zero")
        require_utc(self.scheduled_for, "scheduled_for")
        require_utc(self.created_at, "created_at")
        require_utc(self.updated_at, "updated_at")
        if self.disabled_at is not None:
            require_utc(self.disabled_at, "disabled_at")
        if type(self.duration_seconds) is not int or not (
            1 <= self.duration_seconds <= MAX_PUMP_DURATION_SECONDS
        ):
            raise ValueError(f"duration_seconds must be between 1 and {MAX_PUMP_DURATION_SECONDS}")
        if self.enabled and self.disabled_at is not None:
            raise ValueError("an enabled schedule cannot have disabled_at")


@dataclass(frozen=True, slots=True)
class ScheduleOccurrence:
    occurrence_id: UUID
    schedule_id: UUID
    farm_id: UUID
    device_id: UUID
    scheduled_for: datetime
    duration_seconds: int
    claimed_at: datetime
    status: OccurrenceStatus
    command_id: UUID
    created_at: datetime
    updated_at: datetime
    decision_at: datetime | None = None
    reason_code: str | None = None
    ack_status: str | None = None

    def __post_init__(self) -> None:
        for identifier in (
            self.occurrence_id,
            self.schedule_id,
            self.farm_id,
            self.device_id,
            self.command_id,
        ):
            if identifier.int == 0:
                raise ValueError("occurrence identifiers must be non-zero")
        for field, time_value in (
            ("scheduled_for", self.scheduled_for),
            ("claimed_at", self.claimed_at),
            ("created_at", self.created_at),
            ("updated_at", self.updated_at),
        ):
            require_utc(time_value, field)
        if self.decision_at is not None:
            require_utc(self.decision_at, "decision_at")
        if not 1 <= self.duration_seconds <= MAX_PUMP_DURATION_SECONDS:
            raise ValueError("occurrence duration is outside the wire-contract bounds")


@dataclass(frozen=True, slots=True)
class ScheduleSummary:
    schedule: IrrigationSchedule
    occurrence_status: OccurrenceStatus | None = None
