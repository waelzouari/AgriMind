"""One-cycle AI automatic irrigation with an independent local safety gate."""

from __future__ import annotations

import logging
import math
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from threading import RLock
from typing import Protocol
from uuid import UUID, uuid4, uuid5

from agrimind_edge.config.runtime import AutomaticIrrigationConfig, InferenceConfig
from agrimind_edge.contracts import CommandAcknowledgement, PumpCommand
from agrimind_edge.contracts.enums import AcknowledgementStatus, PumpAction
from agrimind_edge.domain.automatic_irrigation import (
    AutomaticIrrigationResult,
    AutomaticSafetyDecision,
    AutomaticSafetyReason,
)
from agrimind_edge.domain.irrigation_inference import (
    DECISION_THRESHOLD,
    FEATURE_CONTRACT_VERSION,
    MODEL_VERSION,
    InferenceStatus,
    IrrigationRecommendation,
)
from agrimind_edge.domain.pump import PumpState
from agrimind_edge.domain.sensors import ReadingQuality, SensorSnapshot

LOCAL_COMMAND_TTL_SECONDS = 30
AI_REQUESTER_NAMESPACE = UUID("f15d34a4-a225-5e87-9004-3a530d929915")


class Clock(Protocol):
    def now_utc(self) -> datetime: ...


class SnapshotProvider(Protocol):
    def capture(self) -> SensorSnapshot: ...


class InferenceBoundary(Protocol):
    def evaluate(self, snapshot: SensorSnapshot) -> IrrigationRecommendation: ...


class PumpCommandBoundary(Protocol):
    def handle(self, command: PumpCommand) -> CommandAcknowledgement: ...


class PumpStateSource(Protocol):
    @property
    def state(self) -> PumpState: ...


class AutomaticSafetyGate(Protocol):
    def evaluate(
        self,
        correlation_id: str,
        snapshot: SensorSnapshot | None,
        recommendation: IrrigationRecommendation | None,
    ) -> AutomaticSafetyDecision: ...

    def record_accepted(self, accepted_at: datetime) -> None: ...


def automatic_requested_by(farm_id: UUID, device_id: UUID) -> UUID:
    return uuid5(AI_REQUESTER_NAMESPACE, f"{farm_id}:{device_id}:ai_automatic")


class IndependentAutomaticSafetyGate:
    """Independently authorize one AI request without touching the pump."""

    def __init__(
        self,
        config: AutomaticIrrigationConfig,
        inference_config: InferenceConfig,
        pump_state: PumpStateSource,
        clock: Clock,
    ) -> None:
        self._config = config
        self._inference_config = inference_config
        self._pump_state = pump_state
        self._clock = clock
        self._last_accepted_at: datetime | None = None
        self._lock = RLock()

    def evaluate(
        self,
        correlation_id: str,
        snapshot: SensorSnapshot | None,
        recommendation: IrrigationRecommendation | None,
    ) -> AutomaticSafetyDecision:
        try:
            return self._evaluate(correlation_id, snapshot, recommendation)
        except Exception:
            return self._decision(correlation_id, AutomaticSafetyReason.SAFETY_ERROR)

    def record_accepted(self, accepted_at: datetime) -> None:
        """Start cooldown only after AGM-005 accepted physical actuation."""

        _require_utc(accepted_at, "accepted_at")
        with self._lock:
            self._last_accepted_at = accepted_at

    def _evaluate(
        self,
        correlation_id: str,
        snapshot: SensorSnapshot | None,
        recommendation: IrrigationRecommendation | None,
    ) -> AutomaticSafetyDecision:
        now = self._now()
        if not self._config.enabled:
            return self._decision(correlation_id, AutomaticSafetyReason.MODE_DISABLED, now)
        if snapshot is None or recommendation is None:
            return self._decision(correlation_id, AutomaticSafetyReason.INFERENCE_UNAVAILABLE, now)
        if (
            snapshot.correlation_id != correlation_id
            or recommendation.correlation_id != correlation_id
        ):
            return self._decision(correlation_id, AutomaticSafetyReason.RECOMMENDATION_INVALID, now)

        sensor_reason = self._sensor_reason(snapshot, now)
        if sensor_reason is not None:
            return self._decision(correlation_id, sensor_reason, now)
        if not self._recommendation_valid(recommendation, now):
            reason = (
                AutomaticSafetyReason.INFERENCE_UNAVAILABLE
                if recommendation.status is not InferenceStatus.SUCCEEDED
                else AutomaticSafetyReason.RECOMMENDATION_INVALID
            )
            return self._decision(correlation_id, reason, now)
        if recommendation.irrigation_recommended is not True:
            return self._decision(correlation_id, AutomaticSafetyReason.MODEL_NO_IRRIGATION, now)

        state = self._pump_state.state
        if state is PumpState.RUNNING:
            return self._decision(correlation_id, AutomaticSafetyReason.PUMP_RUNNING, now)
        if state is PumpState.FAULT:
            return self._decision(correlation_id, AutomaticSafetyReason.PUMP_FAULT, now)

        with self._lock:
            if self._last_accepted_at is not None:
                if now < self._last_accepted_at:
                    return self._decision(correlation_id, AutomaticSafetyReason.SAFETY_ERROR, now)
                cooldown = self._config.require_cooldown_seconds()
                remaining = cooldown - (now - self._last_accepted_at).total_seconds()
                if remaining > 0:
                    return AutomaticSafetyDecision(
                        allowed=False,
                        reason_code=AutomaticSafetyReason.COOLDOWN_ACTIVE,
                        evaluated_at=now,
                        correlation_id=correlation_id,
                        cooldown_remaining_seconds=remaining,
                    )
        return self._decision(correlation_id, AutomaticSafetyReason.ALLOWED, now)

    def _sensor_reason(
        self, snapshot: SensorSnapshot, now: datetime
    ) -> AutomaticSafetyReason | None:
        required = (snapshot.soil_humidity, snapshot.temperature, snapshot.air_humidity)
        observed: list[datetime] = []
        for measurement in required:
            if measurement.quality is ReadingQuality.STALE:
                return AutomaticSafetyReason.SENSOR_STALE
            if measurement.quality is not ReadingQuality.VALID or measurement.observed_at is None:
                return AutomaticSafetyReason.SENSOR_INVALID
            if measurement.observed_at > now:
                return AutomaticSafetyReason.SENSOR_TIMESTAMP_INVALID
            observed.append(measurement.observed_at)
        if (now - min(observed)).total_seconds() > self._inference_config.max_age_seconds:
            return AutomaticSafetyReason.SENSOR_STALE
        return None

    @staticmethod
    def _recommendation_valid(recommendation: IrrigationRecommendation, now: datetime) -> bool:
        if recommendation.status is not InferenceStatus.SUCCEEDED:
            return False
        return not (
            recommendation.model_version != MODEL_VERSION
            or recommendation.feature_contract_version != FEATURE_CONTRACT_VERSION
            or recommendation.threshold != DECISION_THRESHOLD
            or recommendation.observed_at is None
            or recommendation.observed_at > now
            or recommendation.evaluated_at > now
            or recommendation.score is None
            or not math.isfinite(recommendation.score)
            or recommendation.irrigation_recommended
            != (recommendation.score >= recommendation.threshold)
        )

    def _decision(
        self,
        correlation_id: str,
        reason: AutomaticSafetyReason,
        now: datetime | None = None,
    ) -> AutomaticSafetyDecision:
        return AutomaticSafetyDecision(
            allowed=reason is AutomaticSafetyReason.ALLOWED,
            reason_code=reason,
            evaluated_at=now or self._now(),
            correlation_id=correlation_id,
        )

    def _now(self) -> datetime:
        now = self._clock.now_utc()
        _require_utc(now, "automatic irrigation clock")
        return now


class AutomaticIrrigationService:
    """Evaluate and safely dispatch exactly one automatic irrigation cycle."""

    def __init__(
        self,
        snapshots: SnapshotProvider,
        inference: InferenceBoundary,
        safety_gate: AutomaticSafetyGate,
        command_handler: PumpCommandBoundary,
        config: AutomaticIrrigationConfig,
        clock: Clock,
        *,
        farm_id: UUID,
        device_id: UUID,
        command_id_factory: Callable[[], UUID] | None = None,
        correlation_id_factory: Callable[[], str] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._snapshots = snapshots
        self._inference = inference
        self._safety_gate = safety_gate
        self._command_handler = command_handler
        self._config = config
        self._clock = clock
        self._farm_id = farm_id
        self._device_id = device_id
        self._command_id_factory = command_id_factory or uuid4
        self._correlation_id_factory = correlation_id_factory or (lambda: str(uuid4()))
        self._logger = logger or logging.getLogger(__name__)

    def evaluate_once(self) -> AutomaticIrrigationResult:
        correlation_id = self._correlation_id_factory()
        if not correlation_id.strip():
            raise ValueError("automatic irrigation correlation ID must not be empty")
        if not self._config.enabled:
            return self._blocked(correlation_id, None, None)

        try:
            snapshot = self._snapshots.capture()
        except Exception:
            return self._blocked(correlation_id, None, None)
        correlation_id = snapshot.correlation_id
        try:
            recommendation = self._inference.evaluate(snapshot)
        except Exception:
            return self._blocked(correlation_id, snapshot, None)

        decision = self._evaluate_safety(correlation_id, snapshot, recommendation)
        if not decision.allowed:
            return self._result(correlation_id, recommendation, decision)

        now = self._now()
        command = PumpCommand(
            command_id=self._command_id_factory(),
            farm_id=self._farm_id,
            device_id=self._device_id,
            action=PumpAction.ON,
            issued_at=now,
            expires_at=now + timedelta(seconds=LOCAL_COMMAND_TTL_SECONDS),
            requested_by=automatic_requested_by(self._farm_id, self._device_id),
            duration_seconds=self._config.require_duration_seconds(),
        )
        try:
            acknowledgement = self._command_handler.handle(command)
        except Exception:
            self._log(correlation_id, recommendation, decision, None, "command_failed")
            return self._result(correlation_id, recommendation, decision, submitted=True)
        if acknowledgement.status is AcknowledgementStatus.ACCEPTED:
            self._safety_gate.record_accepted(acknowledgement.occurred_at)
        return self._result(
            correlation_id,
            recommendation,
            decision,
            acknowledgement,
            submitted=True,
        )

    def _blocked(
        self,
        correlation_id: str,
        snapshot: SensorSnapshot | None,
        recommendation: IrrigationRecommendation | None,
    ) -> AutomaticIrrigationResult:
        decision = self._evaluate_safety(correlation_id, snapshot, recommendation)
        return self._result(correlation_id, recommendation, decision)

    def _evaluate_safety(
        self,
        correlation_id: str,
        snapshot: SensorSnapshot | None,
        recommendation: IrrigationRecommendation | None,
    ) -> AutomaticSafetyDecision:
        try:
            return self._safety_gate.evaluate(correlation_id, snapshot, recommendation)
        except Exception:
            return AutomaticSafetyDecision(
                False,
                AutomaticSafetyReason.SAFETY_ERROR,
                self._now(),
                correlation_id,
            )

    def _result(
        self,
        correlation_id: str,
        recommendation: IrrigationRecommendation | None,
        decision: AutomaticSafetyDecision,
        acknowledgement: CommandAcknowledgement | None = None,
        *,
        submitted: bool = False,
    ) -> AutomaticIrrigationResult:
        result = AutomaticIrrigationResult(
            correlation_id,
            recommendation,
            decision,
            submitted,
            acknowledgement,
        )
        self._log(correlation_id, recommendation, decision, acknowledgement, "evaluated")
        return result

    def _now(self) -> datetime:
        now = self._clock.now_utc()
        _require_utc(now, "automatic irrigation clock")
        return now

    def _log(
        self,
        correlation_id: str,
        recommendation: IrrigationRecommendation | None,
        decision: AutomaticSafetyDecision,
        acknowledgement: CommandAcknowledgement | None,
        event: str,
    ) -> None:
        self._logger.info(
            "automatic_irrigation_decision",
            extra={
                "event": event,
                "correlation_id": correlation_id,
                "recommended": (recommendation.irrigation_recommended if recommendation else None),
                "safety_reason": decision.reason_code.value,
                "command_status": (acknowledgement.status.value if acknowledgement else None),
                "command_reason": acknowledgement.reason_code if acknowledgement else None,
            },
        )


def _require_utc(value: datetime, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
        raise ValueError(f"{field} must be timezone-aware UTC")
