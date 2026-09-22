from __future__ import annotations

import logging
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from itertools import count
from uuid import UUID

import pytest

from agrimind_edge.adapters.fake import FakePump, FakeScheduler
from agrimind_edge.application import PumpCommandHandler, SafePumpController
from agrimind_edge.config import PumpSafetyConfig
from agrimind_edge.contracts import CommandAcknowledgement, PumpCommand
from agrimind_edge.contracts.enums import AcknowledgementStatus, PumpAction
from agrimind_edge.domain import PumpState

NOW = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)
FARM_ID = UUID("11111111-1111-4111-8111-111111111111")
DEVICE_ID = UUID("22222222-2222-4222-8222-222222222222")
USER_ID = UUID("55555555-5555-4555-8555-555555555555")


def command(
    action: PumpAction,
    *,
    command_number: int = 10,
    farm_id: UUID = FARM_ID,
    device_id: UUID = DEVICE_ID,
    issued_at: datetime = NOW - timedelta(seconds=1),
    expires_at: datetime = NOW + timedelta(seconds=20),
    duration_seconds: int | None = None,
) -> PumpCommand:
    return PumpCommand(
        command_id=UUID(int=command_number),
        farm_id=farm_id,
        device_id=device_id,
        action=action,
        issued_at=issued_at,
        expires_at=expires_at,
        requested_by=USER_ID,
        duration_seconds=duration_seconds if action is PumpAction.ON else None,
    )


class Harness:
    def __init__(
        self,
        *,
        pump: FakePump | None = None,
        scheduler: FakeScheduler | None = None,
        max_duration: int = 120,
        logger: logging.Logger | None = None,
    ) -> None:
        self.pump = pump or FakePump()
        self.scheduler = scheduler or FakeScheduler()
        self.controller = SafePumpController(self.pump, self.scheduler)
        self.emitted: list[CommandAcknowledgement] = []
        identifiers = count(100)
        self.handler = PumpCommandHandler(
            self.controller,
            PumpSafetyConfig(FARM_ID, DEVICE_ID, max_duration),
            clock=lambda: NOW,
            acknowledgement_id_factory=lambda: UUID(int=next(identifiers)),
            acknowledgement_sink=self.emitted.append,
            logger=logger,
        )


def test_valid_on_is_bounded_and_accepted_only_after_actuation() -> None:
    harness = Harness()

    acknowledgement = harness.handler.handle(command(PumpAction.ON, duration_seconds=30))

    assert acknowledgement.status is AcknowledgementStatus.ACCEPTED
    assert acknowledgement.pump_state is True
    assert harness.controller.state is PumpState.RUNNING
    assert harness.pump.calls.count("turn_on") == 1
    assert len(harness.scheduler.calls) == 1
    assert harness.scheduler.calls[0].delay_seconds == 30
    assert CommandAcknowledgement.from_json(acknowledgement.to_json()) == acknowledgement


def test_automatic_stop_transitions_off_and_emits_completed_ack() -> None:
    harness = Harness()
    on_command = command(PumpAction.ON, duration_seconds=30)
    harness.handler.handle(on_command)

    harness.scheduler.fire_next()

    assert harness.controller.state is PumpState.OFF
    assert harness.pump.active is False
    assert harness.pump.calls.count("turn_off") == 1
    assert len(harness.emitted) == 1
    assert harness.emitted[0].command_id == on_command.command_id
    assert harness.emitted[0].status is AcknowledgementStatus.COMPLETED
    assert harness.emitted[0].pump_state is False


def test_off_stops_running_pump_and_cancels_timer() -> None:
    harness = Harness()
    harness.handler.handle(command(PumpAction.ON, duration_seconds=30))

    acknowledgement = harness.handler.handle(command(PumpAction.OFF, command_number=11))

    assert acknowledgement.status is AcknowledgementStatus.COMPLETED
    assert harness.controller.state is PumpState.OFF
    assert harness.scheduler.calls[0].cancelled is True
    assert harness.pump.calls.count("turn_off") == 1
    harness.scheduler.calls[0].fire()
    assert harness.pump.calls.count("turn_off") == 1


def test_off_while_already_off_is_idempotent_without_reactuation() -> None:
    harness = Harness()
    off_command = command(PumpAction.OFF)

    first = harness.handler.handle(off_command)
    second = harness.handler.handle(off_command)

    assert first is second
    assert first.status is AcknowledgementStatus.COMPLETED
    assert harness.pump.calls == []


def test_duplicate_on_replays_outcome_without_actuating_or_rescheduling() -> None:
    harness = Harness()
    on_command = command(PumpAction.ON, duration_seconds=30)

    first = harness.handler.handle(on_command)
    second = harness.handler.handle(on_command)

    assert second is first
    assert harness.pump.calls.count("turn_on") == 1
    assert len(harness.scheduler.calls) == 1


def test_duplicate_after_automatic_completion_replays_completed_outcome() -> None:
    harness = Harness()
    on_command = command(PumpAction.ON, duration_seconds=30)
    harness.handler.handle(on_command)
    harness.scheduler.fire_next()

    duplicate = harness.handler.handle(on_command)

    assert duplicate is harness.emitted[0]
    assert duplicate.status is AcknowledgementStatus.COMPLETED
    assert harness.pump.calls.count("turn_on") == 1


def test_same_command_id_with_changed_content_is_rejected() -> None:
    harness = Harness()
    original = command(PumpAction.ON, duration_seconds=30)
    harness.handler.handle(original)

    conflict = harness.handler.handle(replace(original, duration_seconds=31))

    assert conflict.status is AcknowledgementStatus.REJECTED
    assert conflict.reason_code == "command_id_conflict"
    assert harness.pump.calls.count("turn_on") == 1


def test_expired_and_future_commands_do_not_actuate() -> None:
    harness = Harness()
    expired = command(
        PumpAction.ON,
        command_number=20,
        issued_at=NOW - timedelta(minutes=1),
        expires_at=NOW,
        duration_seconds=10,
    )
    future = command(
        PumpAction.ON,
        command_number=21,
        issued_at=NOW + timedelta(seconds=1),
        expires_at=NOW + timedelta(seconds=20),
        duration_seconds=10,
    )

    expired_ack = harness.handler.handle(expired)
    future_ack = harness.handler.handle(future)

    assert expired_ack.reason_code == "expired_command"
    assert future_ack.reason_code == "future_command"
    assert expired_ack.status is AcknowledgementStatus.REJECTED
    assert future_ack.status is AcknowledgementStatus.REJECTED
    assert harness.pump.calls == []


def test_duration_above_local_policy_is_rejected_not_clamped() -> None:
    harness = Harness(max_duration=60)

    acknowledgement = harness.handler.handle(command(PumpAction.ON, duration_seconds=61))

    assert acknowledgement.status is AcknowledgementStatus.REJECTED
    assert acknowledgement.reason_code == "duration_exceeds_local_limit"
    assert harness.pump.calls == []
    assert harness.scheduler.calls == []


@pytest.mark.parametrize(
    ("field", "identifier", "reason"),
    [
        ("farm_id", UUID(int=91), "wrong_farm"),
        ("device_id", UUID(int=92), "wrong_device"),
    ],
)
def test_wrong_target_is_rejected_without_actuation(
    field: str, identifier: UUID, reason: str
) -> None:
    harness = Harness()
    targeted = replace(command(PumpAction.ON, duration_seconds=10), **{field: identifier})

    acknowledgement = harness.handler.handle(targeted)

    assert acknowledgement.status is AcknowledgementStatus.REJECTED
    assert acknowledgement.reason_code == reason
    assert acknowledgement.farm_id == FARM_ID
    assert acknowledgement.device_id == DEVICE_ID
    assert harness.pump.calls == []


def test_overlapping_on_is_rejected_and_original_timer_remains() -> None:
    harness = Harness()
    harness.handler.handle(command(PumpAction.ON, duration_seconds=30))

    acknowledgement = harness.handler.handle(
        command(PumpAction.ON, command_number=12, duration_seconds=20)
    )

    assert acknowledgement.status is AcknowledgementStatus.REJECTED
    assert acknowledgement.reason_code == "already_running"
    assert harness.pump.calls.count("turn_on") == 1
    assert len(harness.scheduler.calls) == 1
    assert harness.scheduler.calls[0].cancelled is False


def test_on_actuator_failure_attempts_safe_off_and_returns_failed() -> None:
    pump = FakePump({"turn_on": [RuntimeError("secret hardware detail")]})
    harness = Harness(pump=pump)

    acknowledgement = harness.handler.handle(command(PumpAction.ON, duration_seconds=10))

    assert acknowledgement.status is AcknowledgementStatus.FAILED
    assert acknowledgement.reason_code == "pump_actuation_failed"
    assert acknowledgement.pump_state is False
    assert harness.controller.state is PumpState.OFF
    assert pump.calls.count("turn_on") == 1
    assert pump.calls.count("turn_off") == 1


def test_off_failure_retries_safe_off_but_does_not_claim_completion() -> None:
    pump = FakePump({"turn_off": [RuntimeError("first stop failed")]})
    harness = Harness(pump=pump)
    harness.handler.handle(command(PumpAction.ON, duration_seconds=10))

    acknowledgement = harness.handler.handle(command(PumpAction.OFF, command_number=11))

    assert acknowledgement.status is AcknowledgementStatus.FAILED
    assert acknowledgement.reason_code == "pump_actuation_failed"
    assert acknowledgement.pump_state is False
    assert harness.controller.state is PumpState.OFF
    assert pump.calls.count("turn_off") == 2


def test_automatic_stop_failure_recovers_off_and_emits_failed() -> None:
    pump = FakePump({"turn_off": [RuntimeError("first stop failed")]})
    harness = Harness(pump=pump)
    harness.handler.handle(command(PumpAction.ON, duration_seconds=10))

    harness.scheduler.fire_next()

    assert harness.controller.state is PumpState.OFF
    assert pump.active is False
    assert harness.emitted[0].status is AcknowledgementStatus.FAILED
    assert harness.emitted[0].reason_code == "pump_actuation_failed"
    assert harness.emitted[0].pump_state is False


def test_unrecoverable_automatic_stop_enters_fault_without_false_safe_claim() -> None:
    pump = FakePump({"turn_off": [RuntimeError("stop failed"), RuntimeError("retry failed")]})
    harness = Harness(pump=pump)
    harness.handler.handle(command(PumpAction.ON, duration_seconds=10))

    harness.scheduler.fire_next()

    assert harness.controller.state is PumpState.FAULT
    assert harness.emitted[0].status is AcknowledgementStatus.FAILED
    assert harness.emitted[0].pump_state is None


def test_scheduler_failure_forces_off_and_returns_failed() -> None:
    harness = Harness(scheduler=FakeScheduler(failure=RuntimeError("timer failed")))

    acknowledgement = harness.handler.handle(command(PumpAction.ON, duration_seconds=10))

    assert acknowledgement.status is AcknowledgementStatus.FAILED
    assert acknowledgement.reason_code == "scheduler_failed"
    assert acknowledgement.pump_state is False
    assert harness.controller.state is PumpState.OFF
    assert harness.pump.calls.count("turn_on") == 1
    assert harness.pump.calls.count("turn_off") == 1


def test_acknowledgement_processing_failure_forces_off() -> None:
    pump = FakePump()
    controller = SafePumpController(pump, FakeScheduler())
    calls = count()

    def sometimes_failing_identifier() -> UUID:
        if next(calls) == 0:
            raise RuntimeError("acknowledgement creation failed")
        return UUID(int=100)

    handler = PumpCommandHandler(
        controller,
        PumpSafetyConfig(FARM_ID, DEVICE_ID, 120),
        clock=lambda: NOW,
        acknowledgement_id_factory=sometimes_failing_identifier,
    )

    acknowledgement = handler.handle(command(PumpAction.ON, duration_seconds=10))

    assert acknowledgement.status is AcknowledgementStatus.FAILED
    assert acknowledgement.reason_code == "command_processing_failed"
    assert acknowledgement.pump_state is False
    assert controller.state is PumpState.OFF
    assert pump.calls.count("turn_on") == 1
    assert pump.calls.count("turn_off") == 1


def test_state_inconsistency_is_forced_off_before_rejecting_on() -> None:
    pump = FakePump()
    pump.initialized = True
    pump.active = True
    harness = Harness(pump=pump)

    acknowledgement = harness.handler.handle(command(PumpAction.ON, duration_seconds=10))

    assert acknowledgement.status is AcknowledgementStatus.FAILED
    assert acknowledgement.reason_code == "state_inconsistent"
    assert pump.active is False
    assert pump.calls.count("turn_on") == 0
    assert pump.calls.count("turn_off") == 1


def test_structured_log_uses_stable_fields_not_actuator_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("agrimind.test.pump-command")
    caplog.set_level(logging.INFO, logger=logger.name)
    harness = Harness(
        pump=FakePump({"turn_on": [RuntimeError("credential-like-private-value")]}),
        logger=logger,
    )

    harness.handler.handle(command(PumpAction.ON, duration_seconds=10))

    record = caplog.records[-1]
    assert record.message == "pump_command_decision"
    assert record.command_id == str(UUID(int=10))  # type: ignore[attr-defined]
    assert record.action == "on"  # type: ignore[attr-defined]
    assert record.reason_code == "pump_actuation_failed"  # type: ignore[attr-defined]
    assert "credential-like-private-value" not in caplog.text
