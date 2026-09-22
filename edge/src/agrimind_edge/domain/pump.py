"""Domain types for fail-safe local pump state management."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PumpState(StrEnum):
    OFF = "off"
    RUNNING = "running"
    FAULT = "fault"


class PumpDecisionCode(StrEnum):
    ALREADY_RUNNING = "already_running"
    COMMAND_ID_CONFLICT = "command_id_conflict"
    COMMAND_PROCESSING_FAILED = "command_processing_failed"
    CONTROLLER_FAULT = "controller_fault"
    DURATION_EXCEEDS_LOCAL_LIMIT = "duration_exceeds_local_limit"
    EXPIRED_COMMAND = "expired_command"
    FUTURE_COMMAND = "future_command"
    PUMP_ACTUATION_FAILED = "pump_actuation_failed"
    SCHEDULER_FAILED = "scheduler_failed"
    STATE_INCONSISTENT = "state_inconsistent"
    WRONG_DEVICE = "wrong_device"
    WRONG_FARM = "wrong_farm"


@dataclass(frozen=True, slots=True)
class AutomaticStopResult:
    state: PumpState
    error_code: PumpDecisionCode | None = None

    @property
    def completed(self) -> bool:
        return self.error_code is None and self.state is PumpState.OFF
