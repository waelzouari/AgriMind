"""One-shot scheduled irrigation through the existing safe command boundary."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from threading import Event
from typing import Protocol
from uuid import UUID, uuid4

from agrimind_edge.application.clock import Clock
from agrimind_edge.application.persistence_ports import PersistenceConflict
from agrimind_edge.contracts import CommandAcknowledgement, PumpCommand
from agrimind_edge.contracts.enums import AcknowledgementStatus, PumpAction
from agrimind_edge.domain.schedules import (
    IrrigationSchedule,
    OccurrenceStatus,
    ScheduleOccurrence,
    ScheduleSummary,
    require_utc,
    scheduler_requested_by,
)

LOCAL_COMMAND_TTL_SECONDS = 30


class ScheduleError(RuntimeError):
    """Base error for local schedule operations."""


class DuplicateScheduleError(ScheduleError):
    pass


class ScheduleNotFoundError(ScheduleError):
    pass


class ScheduleTooOldError(ScheduleError):
    pass


class ScheduleRepository(Protocol):
    def create_schedule(self, schedule: IrrigationSchedule) -> None: ...

    def list_schedules(self) -> tuple[ScheduleSummary, ...]: ...

    def disable_schedule(self, schedule_id: UUID, disabled_at: datetime) -> bool: ...

    def claim_due(
        self, now: datetime, max_lateness: timedelta
    ) -> tuple[ScheduleOccurrence, ...]: ...

    def mark_occurrence(
        self,
        occurrence_id: UUID,
        status: OccurrenceStatus,
        decided_at: datetime,
        *,
        reason_code: str | None = None,
        ack_status: str | None = None,
    ) -> None: ...

    def recover_non_terminal(self, recovered_at: datetime) -> int: ...


class PumpCommandBoundary(Protocol):
    def handle(self, command: PumpCommand) -> CommandAcknowledgement: ...


class ScheduledIrrigationService:
    def __init__(
        self,
        repository: ScheduleRepository,
        command_handler: PumpCommandBoundary | None,
        clock: Clock,
        *,
        farm_id: UUID,
        device_id: UUID,
        max_lateness_seconds: int,
        logger: logging.Logger | None = None,
    ) -> None:
        if not 0 <= max_lateness_seconds <= 300:
            raise ValueError("schedule maximum lateness must be between 0 and 300 seconds")
        self._repository = repository
        self._command_handler = command_handler
        self._clock = clock
        self._farm_id = farm_id
        self._device_id = device_id
        self._max_lateness = timedelta(seconds=max_lateness_seconds)
        self._logger = logger or logging.getLogger(__name__)

    def create_schedule(
        self,
        scheduled_for: object,
        duration_seconds: int,
        *,
        schedule_id: UUID | None = None,
    ) -> IrrigationSchedule:
        if not isinstance(scheduled_for, datetime):
            raise ValueError("scheduled_for must be a datetime")
        require_utc(scheduled_for, "scheduled_for")
        now = self._clock.now_utc()
        if scheduled_for < now - self._max_lateness:
            raise ScheduleTooOldError("schedule_too_old")
        schedule = IrrigationSchedule(
            schedule_id=schedule_id or uuid4(),
            farm_id=self._farm_id,
            device_id=self._device_id,
            scheduled_for=scheduled_for,
            duration_seconds=duration_seconds,
            enabled=True,
            created_at=now,
            updated_at=now,
        )
        try:
            self._repository.create_schedule(schedule)
        except PersistenceConflict as error:
            raise DuplicateScheduleError("duplicate_schedule") from error
        self._log("schedule_created", schedule=schedule)
        return schedule

    def list_schedules(self) -> tuple[ScheduleSummary, ...]:
        return self._repository.list_schedules()

    def disable_schedule(self, schedule_id: UUID) -> None:
        now = self._clock.now_utc()
        if not self._repository.disable_schedule(schedule_id, now):
            raise ScheduleNotFoundError("schedule_not_found")
        self._logger.info(
            "schedule_disabled",
            extra={"event": "schedule_disabled", "schedule_id": str(schedule_id)},
        )

    def recover(self) -> int:
        recovered = self._repository.recover_non_terminal(self._clock.now_utc())
        if recovered:
            self._logger.warning(
                "schedule_recovery",
                extra={"event": "schedule_recovery", "occurrences": recovered},
            )
        return recovered

    def process_due(self) -> tuple[ScheduleOccurrence, ...]:
        if self._command_handler is None:
            raise RuntimeError("pump command handler is required to process due schedules")
        now = self._clock.now_utc()
        occurrences = self._repository.claim_due(now, self._max_lateness)
        for occurrence in occurrences:
            if occurrence.status is OccurrenceStatus.MISSED:
                self._log("schedule_missed", occurrence=occurrence)
                continue
            self._dispatch(occurrence)
        return occurrences

    def _dispatch(self, occurrence: ScheduleOccurrence) -> None:
        issued_at = self._clock.now_utc()
        command = PumpCommand(
            command_id=occurrence.command_id,
            farm_id=occurrence.farm_id,
            device_id=occurrence.device_id,
            action=PumpAction.ON,
            issued_at=issued_at,
            expires_at=issued_at + timedelta(seconds=LOCAL_COMMAND_TTL_SECONDS),
            requested_by=scheduler_requested_by(occurrence.farm_id, occurrence.device_id),
            duration_seconds=occurrence.duration_seconds,
        )
        try:
            if self._command_handler is None:  # guarded by process_due
                raise RuntimeError("pump command handler is unavailable")
            acknowledgement = self._command_handler.handle(command)
        except Exception:
            self._repository.mark_occurrence(
                occurrence.occurrence_id,
                OccurrenceStatus.FAILED,
                self._clock.now_utc(),
                reason_code="command_handler_failed_before_acknowledgement",
            )
            self._log(
                "schedule_command_failed",
                occurrence=occurrence,
                reason_code="command_handler_failed_before_acknowledgement",
            )
            return

        if acknowledgement.status is AcknowledgementStatus.ACCEPTED:
            try:
                self._repository.mark_occurrence(
                    occurrence.occurrence_id,
                    OccurrenceStatus.COMMAND_ACCEPTED,
                    self._clock.now_utc(),
                    reason_code=acknowledgement.reason_code,
                    ack_status=acknowledgement.status.value,
                )
            except Exception:
                self._repository.mark_occurrence(
                    occurrence.occurrence_id,
                    OccurrenceStatus.UNKNOWN_AFTER_ACCEPTANCE,
                    self._clock.now_utc(),
                    reason_code="accepted_outcome_persistence_failed",
                    ack_status=acknowledgement.status.value,
                )
                self._log(
                    "schedule_command_outcome_uncertain",
                    occurrence=occurrence,
                    reason_code="accepted_outcome_persistence_failed",
                )
                return
            self._log(
                "schedule_command_accepted",
                occurrence=occurrence,
                reason_code=acknowledgement.reason_code,
            )
            return

        status = (
            OccurrenceStatus.REJECTED
            if acknowledgement.status is AcknowledgementStatus.REJECTED
            else OccurrenceStatus.FAILED
        )
        event = (
            "schedule_command_rejected"
            if status is OccurrenceStatus.REJECTED
            else "schedule_command_failed"
        )
        self._repository.mark_occurrence(
            occurrence.occurrence_id,
            status,
            self._clock.now_utc(),
            reason_code=acknowledgement.reason_code,
            ack_status=acknowledgement.status.value,
        )
        self._log(event, occurrence=occurrence, reason_code=acknowledgement.reason_code)

    def _log(
        self,
        event: str,
        *,
        schedule: IrrigationSchedule | None = None,
        occurrence: ScheduleOccurrence | None = None,
        reason_code: str | None = None,
    ) -> None:
        if schedule is None and occurrence is None:
            raise ValueError("schedule log context is required")
        if schedule is not None:
            schedule_id = schedule.schedule_id
            scheduled_for = schedule.scheduled_for
            duration_seconds = schedule.duration_seconds
        else:
            assert occurrence is not None
            schedule_id = occurrence.schedule_id
            scheduled_for = occurrence.scheduled_for
            duration_seconds = occurrence.duration_seconds
        self._logger.info(
            event,
            extra={
                "event": event,
                "schedule_id": str(schedule_id),
                "occurrence_id": str(occurrence.occurrence_id) if occurrence else None,
                "command_id": str(occurrence.command_id) if occurrence else None,
                "farm_id": str(occurrence.farm_id if occurrence is not None else self._farm_id),
                "device_id": str(
                    occurrence.device_id if occurrence is not None else self._device_id
                ),
                "scheduled_for": scheduled_for.isoformat(),
                "duration_seconds": duration_seconds,
                "reason_code": reason_code,
            },
        )


class ScheduledIrrigationRunner:
    def __init__(
        self,
        service: ScheduledIrrigationService,
        *,
        enabled: bool,
        poll_interval_seconds: float,
        logger: logging.Logger | None = None,
    ) -> None:
        if not 0.5 <= poll_interval_seconds <= 60:
            raise ValueError("scheduler poll interval must be between 0.5 and 60 seconds")
        self._service = service
        self._enabled = enabled
        self._poll_interval_seconds = poll_interval_seconds
        self._logger = logger or logging.getLogger(__name__)

    def tick(self) -> tuple[ScheduleOccurrence, ...]:
        if not self._enabled:
            return ()
        return self._service.process_due()

    def run(self, stop_event: Event) -> None:
        if not self._enabled:
            raise RuntimeError("scheduler_disabled")
        self._logger.info("scheduler_started", extra={"event": "scheduler_started"})
        try:
            while not stop_event.is_set():
                self.tick()
                stop_event.wait(self._poll_interval_seconds)
        except Exception:
            self._logger.error("scheduler_fatal", extra={"event": "scheduler_fatal"})
            raise
        finally:
            self._logger.info("scheduler_stopped", extra={"event": "scheduler_stopped"})
