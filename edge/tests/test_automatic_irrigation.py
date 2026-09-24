from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from agrimind_edge.adapters.fake import FakePump, FakeScheduler
from agrimind_edge.application.automatic_irrigation import (
    AutomaticIrrigationService,
    IndependentAutomaticSafetyGate,
    automatic_requested_by,
)
from agrimind_edge.application.pump_command_handler import PumpCommandHandler
from agrimind_edge.application.pump_controller import SafePumpController
from agrimind_edge.config import (
    AutomaticIrrigationConfig,
    InferenceConfig,
    PumpSafetyConfig,
)
from agrimind_edge.contracts import CommandAcknowledgement, PumpCommand
from agrimind_edge.contracts.enums import AcknowledgementStatus, PumpAction
from agrimind_edge.domain import (
    DECISION_THRESHOLD,
    AutomaticSafetyDecision,
    AutomaticSafetyReason,
    InferenceReasonCode,
    InferenceStatus,
    IrrigationRecommendation,
    Measurement,
    PumpState,
    ReadingQuality,
    SensorError,
    SensorErrorCode,
    SensorSnapshot,
)
from agrimind_edge.domain.schedules import scheduler_requested_by

NOW = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)
FARM_ID = UUID("11111111-1111-4111-8111-111111111111")
DEVICE_ID = UUID("22222222-2222-4222-8222-222222222222")
COMMAND_ID = UUID("33333333-3333-4333-8333-333333333333")
ACK_ID = UUID("44444444-4444-4444-8444-444444444444")


class FakeClock:
    def __init__(self, now: datetime = NOW) -> None:
        self.current = now

    def now_utc(self) -> datetime:
        return self.current

    def advance(self, seconds: int) -> None:
        self.current += timedelta(seconds=seconds)


class FakePumpState:
    def __init__(self, state: PumpState = PumpState.OFF) -> None:
        self.state = state


class FailingPumpState:
    @property
    def state(self) -> PumpState:
        raise RuntimeError("synthetic pump-state failure")


class FakeSnapshots:
    def __init__(self, value: SensorSnapshot | Exception) -> None:
        self.value = value
        self.calls = 0

    def capture(self) -> SensorSnapshot:
        self.calls += 1
        if isinstance(self.value, Exception):
            raise self.value
        return self.value


class FakeInference:
    def __init__(self, value: IrrigationRecommendation | Exception) -> None:
        self.value = value
        self.calls = 0

    def evaluate(self, snapshot: SensorSnapshot) -> IrrigationRecommendation:
        self.calls += 1
        if isinstance(self.value, Exception):
            raise self.value
        return self.value


class FakeCommands:
    def __init__(self, status: AcknowledgementStatus = AcknowledgementStatus.ACCEPTED) -> None:
        self.status = status
        self.commands: list[PumpCommand] = []
        self.error: Exception | None = None

    def handle(self, command: PumpCommand) -> CommandAcknowledgement:
        self.commands.append(command)
        if self.error is not None:
            raise self.error
        reason = (
            "already_running"
            if self.status in {AcknowledgementStatus.REJECTED, AcknowledgementStatus.FAILED}
            else None
        )
        return CommandAcknowledgement(
            acknowledgement_id=ACK_ID,
            command_id=command.command_id,
            farm_id=command.farm_id,
            device_id=command.device_id,
            status=self.status,
            occurred_at=NOW,
            reason_code=reason,
            pump_state=self.status is AcknowledgementStatus.ACCEPTED,
        )


class FailingGate:
    def evaluate(
        self,
        correlation_id: str,
        snapshot: SensorSnapshot | None,
        recommendation: IrrigationRecommendation | None,
    ) -> AutomaticSafetyDecision:
        del correlation_id, snapshot, recommendation
        raise RuntimeError("synthetic safety failure")

    def record_accepted(self, accepted_at: datetime) -> None:
        del accepted_at


def measurement(
    value: float | None,
    unit: str,
    *,
    quality: ReadingQuality = ReadingQuality.VALID,
    observed_at: datetime | None = NOW,
) -> Measurement:
    error = None
    if quality is not ReadingQuality.VALID:
        error = SensorError(SensorErrorCode.INVALID_READING, "test sensor state")
    return Measurement(value, unit, quality, observed_at, error)


def snapshot(
    *,
    soil: Measurement | None = None,
    correlation_id: str = "corr-024",
    observed_at: datetime = NOW,
) -> SensorSnapshot:
    return SensorSnapshot(
        captured_at=NOW,
        correlation_id=correlation_id,
        temperature=measurement(25.0, "celsius", observed_at=observed_at),
        air_humidity=measurement(60.0, "percent", observed_at=observed_at),
        soil_humidity=soil or measurement(45.0, "percent", observed_at=observed_at),
        soil_raw=measurement(20_000.0, "adc_raw"),
        tank_distance=measurement(8.0, "centimeter"),
        tank_water_level=measurement(20.0, "centimeter"),
        tank_water_percent=measurement(0.0, "percent"),
    )


def recommendation(
    *,
    recommended: bool | None = True,
    score: float | None = 0.94,
    status: InferenceStatus = InferenceStatus.SUCCEEDED,
    reason: InferenceReasonCode | None = None,
    correlation_id: str = "corr-024",
    evaluated_at: datetime = NOW,
) -> IrrigationRecommendation:
    return IrrigationRecommendation(
        model_version="irrigation-baseline-v1",
        feature_contract_version="v1",
        observed_at=evaluated_at if status is InferenceStatus.SUCCEEDED else None,
        evaluated_at=evaluated_at,
        correlation_id=correlation_id,
        score=score,
        threshold=DECISION_THRESHOLD,
        irrigation_recommended=recommended,
        status=status,
        reason_code=reason,
    )


def enabled_config() -> AutomaticIrrigationConfig:
    return AutomaticIrrigationConfig(True, duration_seconds=10, cooldown_seconds=60)


def gate(
    clock: FakeClock,
    state: FakePumpState | FailingPumpState | SafePumpController | None = None,
    config: AutomaticIrrigationConfig | None = None,
) -> IndependentAutomaticSafetyGate:
    return IndependentAutomaticSafetyGate(
        config or enabled_config(),
        InferenceConfig(max_age_seconds=30),
        state or FakePumpState(),
        clock,
    )


def service(
    clock: FakeClock,
    *,
    config: AutomaticIrrigationConfig | None = None,
    snapshots: FakeSnapshots | None = None,
    inference: FakeInference | None = None,
    commands: FakeCommands | None = None,
    safety_gate: IndependentAutomaticSafetyGate | FailingGate | None = None,
) -> tuple[AutomaticIrrigationService, FakeSnapshots, FakeInference, FakeCommands]:
    resolved_config = config or enabled_config()
    fake_snapshots = snapshots or FakeSnapshots(snapshot())
    fake_inference = inference or FakeInference(recommendation())
    fake_commands = commands or FakeCommands()
    app = AutomaticIrrigationService(
        fake_snapshots,
        fake_inference,
        safety_gate or gate(clock, config=resolved_config),
        fake_commands,
        resolved_config,
        clock,
        farm_id=FARM_ID,
        device_id=DEVICE_ID,
        command_id_factory=lambda: COMMAND_ID,
        correlation_id_factory=lambda: "cycle-024",
    )
    return app, fake_snapshots, fake_inference, fake_commands


def test_disabled_mode_blocks_before_sensor_capture() -> None:
    clock = FakeClock()
    disabled = AutomaticIrrigationConfig()
    app, snapshots, inference, commands = service(clock, config=disabled)

    result = app.evaluate_once()

    assert result.safety_decision.reason_code is AutomaticSafetyReason.MODE_DISABLED
    assert snapshots.calls == inference.calls == 0
    assert commands.commands == []


def test_positive_recommendation_submits_canonical_local_command() -> None:
    app, _, _, commands = service(FakeClock())

    result = app.evaluate_once()

    assert result.command_submitted is True
    assert result.command_acknowledgement is not None
    assert result.command_acknowledgement.status is AcknowledgementStatus.ACCEPTED
    command = commands.commands[0]
    assert command.action is PumpAction.ON
    assert command.duration_seconds == 10
    assert command.farm_id == FARM_ID
    assert command.device_id == DEVICE_ID
    assert command.requested_by == automatic_requested_by(FARM_ID, DEVICE_ID)
    assert command.expires_at - command.issued_at == timedelta(seconds=30)


def test_positive_cycle_reaches_existing_agm005_handler_with_fake_hardware() -> None:
    clock = FakeClock()
    pump = FakePump()
    controller = SafePumpController(pump, FakeScheduler())
    handler = PumpCommandHandler(
        controller,
        PumpSafetyConfig(FARM_ID, DEVICE_ID, 120),
        clock=clock.now_utc,
        acknowledgement_id_factory=lambda: ACK_ID,
    )
    safety = gate(clock, controller)
    app = AutomaticIrrigationService(
        FakeSnapshots(snapshot()),
        FakeInference(recommendation()),
        safety,
        handler,
        enabled_config(),
        clock,
        farm_id=FARM_ID,
        device_id=DEVICE_ID,
        command_id_factory=lambda: COMMAND_ID,
    )

    result = app.evaluate_once()

    assert result.command_acknowledgement is not None
    assert result.command_acknowledgement.status is AcknowledgementStatus.ACCEPTED
    assert controller.state is PumpState.RUNNING
    assert pump.active is True


@pytest.mark.parametrize(
    "active_requester",
    [
        UUID("55555555-5555-4555-8555-555555555555"),
        scheduler_requested_by(FARM_ID, DEVICE_ID),
        automatic_requested_by(FARM_ID, DEVICE_ID),
    ],
    ids=["manual", "scheduled", "ai"],
)
def test_ai_cycle_cannot_overlap_manual_scheduled_or_ai_actuation(
    active_requester: UUID,
) -> None:
    clock = FakeClock()
    pump = FakePump()
    controller = SafePumpController(pump, FakeScheduler())
    handler = PumpCommandHandler(
        controller,
        PumpSafetyConfig(FARM_ID, DEVICE_ID, 120),
        clock=clock.now_utc,
        acknowledgement_id_factory=lambda: ACK_ID,
    )
    active = PumpCommand(
        command_id=UUID("66666666-6666-4666-8666-666666666666"),
        farm_id=FARM_ID,
        device_id=DEVICE_ID,
        action=PumpAction.ON,
        issued_at=NOW,
        expires_at=NOW + timedelta(seconds=30),
        requested_by=active_requester,
        duration_seconds=30,
    )
    assert handler.handle(active).status is AcknowledgementStatus.ACCEPTED
    app = AutomaticIrrigationService(
        FakeSnapshots(snapshot()),
        FakeInference(recommendation()),
        gate(clock, controller),
        handler,
        enabled_config(),
        clock,
        farm_id=FARM_ID,
        device_id=DEVICE_ID,
    )

    result = app.evaluate_once()

    assert result.safety_decision.reason_code is AutomaticSafetyReason.PUMP_RUNNING
    assert result.command_submitted is False
    assert pump.calls.count("turn_on") == 1


@pytest.mark.parametrize(
    ("value", "reason"),
    [
        (recommendation(recommended=False, score=0.0), AutomaticSafetyReason.MODEL_NO_IRRIGATION),
        (
            recommendation(
                recommended=None,
                score=None,
                status=InferenceStatus.MODEL_UNAVAILABLE,
                reason=InferenceReasonCode.MODEL_UNAVAILABLE,
            ),
            AutomaticSafetyReason.INFERENCE_UNAVAILABLE,
        ),
    ],
)
def test_negative_or_unavailable_inference_never_submits_command(
    value: IrrigationRecommendation, reason: AutomaticSafetyReason
) -> None:
    app, _, _, commands = service(FakeClock(), inference=FakeInference(value))

    result = app.evaluate_once()

    assert result.safety_decision.reason_code is reason
    assert result.command_submitted is False
    assert commands.commands == []


def test_capture_and_inference_exceptions_fail_closed() -> None:
    capture_app, _, _, capture_commands = service(
        FakeClock(), snapshots=FakeSnapshots(RuntimeError("capture failed"))
    )
    inference_app, _, _, inference_commands = service(
        FakeClock(), inference=FakeInference(RuntimeError("inference failed"))
    )

    assert (
        capture_app.evaluate_once().safety_decision.reason_code
        is AutomaticSafetyReason.INFERENCE_UNAVAILABLE
    )
    assert (
        inference_app.evaluate_once().safety_decision.reason_code
        is AutomaticSafetyReason.INFERENCE_UNAVAILABLE
    )
    assert capture_commands.commands == inference_commands.commands == []


def test_safety_gate_exception_fails_closed() -> None:
    app, _, _, commands = service(FakeClock(), safety_gate=FailingGate())

    result = app.evaluate_once()

    assert result.safety_decision.reason_code is AutomaticSafetyReason.SAFETY_ERROR
    assert commands.commands == []


def test_safety_dependency_failure_is_converted_to_safe_block() -> None:
    clock = FakeClock()
    safety = gate(clock, FailingPumpState())

    decision = safety.evaluate("corr-024", snapshot(), recommendation())

    assert decision.reason_code is AutomaticSafetyReason.SAFETY_ERROR


def test_disabled_mode_still_contains_safety_gate_exception() -> None:
    clock = FakeClock()
    disabled = AutomaticIrrigationConfig()
    app, snapshots, _, commands = service(
        clock,
        config=disabled,
        safety_gate=FailingGate(),
    )

    result = app.evaluate_once()

    assert result.safety_decision.reason_code is AutomaticSafetyReason.SAFETY_ERROR
    assert snapshots.calls == 0
    assert commands.commands == []


@pytest.mark.parametrize(
    ("state", "reason"),
    [
        (PumpState.RUNNING, AutomaticSafetyReason.PUMP_RUNNING),
        (PumpState.FAULT, AutomaticSafetyReason.PUMP_FAULT),
    ],
)
def test_manual_scheduled_or_ai_running_state_blocks_before_command(
    state: PumpState, reason: AutomaticSafetyReason
) -> None:
    clock = FakeClock()
    app, _, _, commands = service(clock, safety_gate=gate(clock, FakePumpState(state)))

    result = app.evaluate_once()

    assert result.safety_decision.reason_code is reason
    assert commands.commands == []


def test_stale_and_invalid_sensor_state_are_independently_blocked() -> None:
    stale = measurement(
        45.0,
        "percent",
        quality=ReadingQuality.STALE,
        observed_at=NOW - timedelta(seconds=10),
    )
    stale_gate = gate(FakeClock())
    invalid_gate = gate(FakeClock())

    stale_decision = stale_gate.evaluate("corr-024", snapshot(soil=stale), recommendation())
    invalid_decision = invalid_gate.evaluate(
        "corr-024",
        snapshot(
            soil=measurement(None, "percent", quality=ReadingQuality.FAILED, observed_at=None)
        ),
        recommendation(),
    )

    assert stale_decision.reason_code is AutomaticSafetyReason.SENSOR_STALE
    assert invalid_decision.reason_code is AutomaticSafetyReason.SENSOR_INVALID


def test_future_and_expired_sensor_timestamps_are_blocked() -> None:
    clock = FakeClock()
    safety = gate(clock)
    future = snapshot(soil=measurement(45.0, "percent", observed_at=NOW + timedelta(seconds=1)))
    old = snapshot(soil=measurement(45.0, "percent", observed_at=NOW - timedelta(seconds=31)))

    assert (
        safety.evaluate("corr-024", future, recommendation()).reason_code
        is AutomaticSafetyReason.SENSOR_TIMESTAMP_INVALID
    )
    assert (
        safety.evaluate("corr-024", old, recommendation()).reason_code
        is AutomaticSafetyReason.SENSOR_STALE
    )


def test_malformed_recommendation_metadata_is_blocked() -> None:
    invalid = replace(recommendation(), model_version="other-model")

    decision = gate(FakeClock()).evaluate("corr-024", snapshot(), invalid)

    assert decision.reason_code is AutomaticSafetyReason.RECOMMENDATION_INVALID


def test_defensive_gate_rejects_missing_score_in_forged_success_result() -> None:
    invalid = recommendation()
    object.__setattr__(invalid, "score", None)

    decision = gate(FakeClock()).evaluate("corr-024", snapshot(), invalid)

    assert decision.reason_code is AutomaticSafetyReason.RECOMMENDATION_INVALID


def test_negative_inference_and_safety_block_do_not_start_cooldown() -> None:
    clock = FakeClock()
    state = FakePumpState()
    safety = gate(clock, state)

    negative = safety.evaluate(
        "corr-024",
        snapshot(),
        recommendation(recommended=False, score=0.0),
    )
    assert negative.reason_code is AutomaticSafetyReason.MODEL_NO_IRRIGATION

    state.state = PumpState.RUNNING
    busy = safety.evaluate("corr-024", snapshot(), recommendation())
    assert busy.reason_code is AutomaticSafetyReason.PUMP_RUNNING

    state.state = PumpState.OFF
    allowed = safety.evaluate("corr-024", snapshot(), recommendation())
    assert allowed.reason_code is AutomaticSafetyReason.ALLOWED


def test_cooldown_starts_only_after_accepted_command_and_expires_deterministically() -> None:
    clock = FakeClock()
    safety = gate(clock)
    app, snapshots, inference, commands = service(clock, safety_gate=safety)

    assert app.evaluate_once().command_acknowledgement is not None
    blocked = app.evaluate_once()
    assert blocked.safety_decision.reason_code is AutomaticSafetyReason.COOLDOWN_ACTIVE
    assert len(commands.commands) == 1

    clock.advance(60)
    snapshots.value = snapshot(observed_at=clock.current)
    inference.value = recommendation(evaluated_at=clock.current)
    allowed = app.evaluate_once()
    assert allowed.command_acknowledgement is not None
    assert len(commands.commands) == 2


@pytest.mark.parametrize(
    "status",
    [AcknowledgementStatus.REJECTED, AcknowledgementStatus.FAILED],
)
def test_rejected_or_failed_command_does_not_start_cooldown(
    status: AcknowledgementStatus,
) -> None:
    clock = FakeClock()
    commands = FakeCommands(status)
    app, _, _, _ = service(clock, commands=commands)

    first = app.evaluate_once()
    second = app.evaluate_once()

    assert first.command_acknowledgement is not None
    assert second.safety_decision.allowed is True
    assert len(commands.commands) == 2


def test_command_boundary_exception_is_submitted_but_does_not_start_cooldown() -> None:
    clock = FakeClock()
    commands = FakeCommands()
    commands.error = RuntimeError("command boundary failed")
    app, _, _, _ = service(clock, commands=commands)

    first = app.evaluate_once()
    second = app.evaluate_once()

    assert first.command_submitted is True
    assert first.command_acknowledgement is None
    assert second.safety_decision.allowed is True
    assert len(commands.commands) == 2


def test_low_reservoir_value_is_monitoring_only() -> None:
    decision = gate(FakeClock()).evaluate("corr-024", snapshot(), recommendation())

    assert decision.allowed is True
