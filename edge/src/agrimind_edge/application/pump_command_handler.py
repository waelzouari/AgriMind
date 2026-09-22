"""Transport-independent local validation and pump-command processing."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from threading import RLock
from uuid import UUID, uuid4

from agrimind_edge.application.pump_controller import (
    PumpOperationFailed,
    PumpTransitionRejected,
    SafePumpController,
)
from agrimind_edge.config.runtime import PumpSafetyConfig
from agrimind_edge.contracts import CommandAcknowledgement, PumpCommand
from agrimind_edge.contracts.enums import AcknowledgementStatus, PumpAction
from agrimind_edge.domain.pump import AutomaticStopResult, PumpDecisionCode, PumpState

AcknowledgementSink = Callable[[CommandAcknowledgement], None]


class PumpCommandHandler:
    """Authorize local targets, deduplicate commands, and invoke the safety controller."""

    def __init__(
        self,
        controller: SafePumpController,
        config: PumpSafetyConfig,
        *,
        clock: Callable[[], datetime] | None = None,
        acknowledgement_id_factory: Callable[[], UUID] | None = None,
        acknowledgement_sink: AcknowledgementSink | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._controller = controller
        self._config = config
        self._clock = clock or (lambda: datetime.now(UTC))
        self._acknowledgement_id_factory = acknowledgement_id_factory or uuid4
        self._acknowledgement_sink = acknowledgement_sink or (lambda acknowledgement: None)
        self._logger = logger or logging.getLogger(__name__)
        self._outcomes: dict[UUID, tuple[PumpCommand, CommandAcknowledgement]] = {}
        self._lock = RLock()

    def handle(self, command: PumpCommand) -> CommandAcknowledgement:
        """Process one already-deserialized v1 command without transport concerns."""

        with self._lock:
            target_error = self._target_error(command)
            if target_error is not None:
                return self._reject(command, target_error, remember=False)

            previous = self._outcomes.get(command.command_id)
            if previous is not None:
                previous_command, acknowledgement = previous
                if previous_command == command:
                    self._log(command, "duplicate_replayed", acknowledgement)
                    return acknowledgement
                return self._reject(command, PumpDecisionCode.COMMAND_ID_CONFLICT, remember=False)

            now = self._now()
            if command.issued_at > now:
                return self._reject(command, PumpDecisionCode.FUTURE_COMMAND)
            if command.expires_at <= now:
                return self._reject(command, PumpDecisionCode.EXPIRED_COMMAND)
            if (
                command.action is PumpAction.ON
                and command.duration_seconds is not None
                and command.duration_seconds > self._config.max_duration_seconds
            ):
                return self._reject(command, PumpDecisionCode.DURATION_EXCEEDS_LOCAL_LIMIT)

            try:
                if command.action is PumpAction.ON:
                    duration = command.duration_seconds
                    if duration is None:  # protected by PumpCommand, kept fail-safe
                        return self._reject(command, PumpDecisionCode.COMMAND_PROCESSING_FAILED)
                    self._controller.start(
                        duration,
                        lambda result: self._on_automatic_stop(command, result),
                    )
                    acknowledgement = self._ack(command, AcknowledgementStatus.ACCEPTED, True)
                else:
                    self._controller.stop()
                    acknowledgement = self._ack(command, AcknowledgementStatus.COMPLETED, False)
            except PumpTransitionRejected as error:
                return self._reject(command, error.code)
            except PumpOperationFailed as error:
                acknowledgement = self._ack(
                    command,
                    AcknowledgementStatus.FAILED,
                    False if error.safe_off else None,
                    error.code,
                )
            except Exception:
                safe_off = self._controller.force_safe_off()
                acknowledgement = self._ack(
                    command,
                    AcknowledgementStatus.FAILED,
                    False if safe_off else None,
                    PumpDecisionCode.COMMAND_PROCESSING_FAILED,
                )

            self._outcomes[command.command_id] = (command, acknowledgement)
            self._log(command, "processed", acknowledgement)
            return acknowledgement

    def _on_automatic_stop(self, command: PumpCommand, result: AutomaticStopResult) -> None:
        with self._lock:
            if result.completed:
                acknowledgement = self._ack(command, AcknowledgementStatus.COMPLETED, False)
            else:
                acknowledgement = self._ack(
                    command,
                    AcknowledgementStatus.FAILED,
                    False if result.state is PumpState.OFF else None,
                    result.error_code or PumpDecisionCode.PUMP_ACTUATION_FAILED,
                )
            self._outcomes[command.command_id] = (command, acknowledgement)
            self._log(command, "automatic_stop", acknowledgement)
            self._acknowledgement_sink(acknowledgement)

    def _target_error(self, command: PumpCommand) -> PumpDecisionCode | None:
        if command.farm_id != self._config.farm_id:
            return PumpDecisionCode.WRONG_FARM
        if command.device_id != self._config.device_id:
            return PumpDecisionCode.WRONG_DEVICE
        return None

    def _reject(
        self,
        command: PumpCommand,
        code: PumpDecisionCode,
        *,
        remember: bool = True,
    ) -> CommandAcknowledgement:
        acknowledgement = self._ack(
            command,
            AcknowledgementStatus.REJECTED,
            self._controller.state is PumpState.RUNNING,
            code,
        )
        if remember:
            self._outcomes[command.command_id] = (command, acknowledgement)
        self._log(command, "rejected", acknowledgement)
        return acknowledgement

    def _ack(
        self,
        command: PumpCommand,
        status: AcknowledgementStatus,
        pump_state: bool | None,
        reason: PumpDecisionCode | None = None,
    ) -> CommandAcknowledgement:
        return CommandAcknowledgement(
            acknowledgement_id=self._acknowledgement_id_factory(),
            command_id=command.command_id,
            farm_id=self._config.farm_id,
            device_id=self._config.device_id,
            status=status,
            occurred_at=self._now(),
            reason_code=reason.value if reason is not None else None,
            pump_state=pump_state,
        )

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() != UTC.utcoffset(now):
            raise ValueError("pump command clock must return UTC")
        return now

    def _log(
        self,
        command: PumpCommand,
        decision: str,
        acknowledgement: CommandAcknowledgement,
    ) -> None:
        self._logger.info(
            "pump_command_decision",
            extra={
                "event": "pump_command_decision",
                "correlation_id": str(acknowledgement.acknowledgement_id),
                "command_id": str(command.command_id),
                "action": command.action.value,
                "decision": decision,
                "status": acknowledgement.status.value,
                "reason_code": acknowledgement.reason_code,
                "resulting_state": self._controller.state.value,
            },
        )
