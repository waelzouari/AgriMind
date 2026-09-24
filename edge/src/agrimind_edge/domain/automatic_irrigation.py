"""Domain decisions for fail-safe AI automatic irrigation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from agrimind_edge.contracts import CommandAcknowledgement
from agrimind_edge.domain.irrigation_inference import IrrigationRecommendation


class AutomaticSafetyReason(StrEnum):
    ALLOWED = "allowed"
    MODE_DISABLED = "mode_disabled"
    INFERENCE_UNAVAILABLE = "inference_unavailable"
    MODEL_NO_IRRIGATION = "model_no_irrigation"
    RECOMMENDATION_INVALID = "recommendation_invalid"
    SENSOR_INVALID = "sensor_invalid"
    SENSOR_STALE = "sensor_stale"
    SENSOR_TIMESTAMP_INVALID = "sensor_timestamp_invalid"
    PUMP_RUNNING = "pump_running"
    PUMP_FAULT = "pump_fault"
    COOLDOWN_ACTIVE = "cooldown_active"
    SAFETY_ERROR = "safety_error"


def _require_utc(value: datetime, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
        raise ValueError(f"{field} must be timezone-aware UTC")


@dataclass(frozen=True, slots=True)
class AutomaticSafetyDecision:
    allowed: bool
    reason_code: AutomaticSafetyReason
    evaluated_at: datetime
    correlation_id: str
    cooldown_remaining_seconds: float | None = None

    def __post_init__(self) -> None:
        _require_utc(self.evaluated_at, "evaluated_at")
        if not self.correlation_id.strip():
            raise ValueError("correlation_id must not be empty")
        if self.allowed != (self.reason_code is AutomaticSafetyReason.ALLOWED):
            raise ValueError("allowed must match the safety reason")
        if self.cooldown_remaining_seconds is not None and (
            self.reason_code is not AutomaticSafetyReason.COOLDOWN_ACTIVE
            or self.cooldown_remaining_seconds <= 0
        ):
            raise ValueError("cooldown remaining is valid only for an active cooldown")
        if (
            self.reason_code is AutomaticSafetyReason.COOLDOWN_ACTIVE
            and self.cooldown_remaining_seconds is None
        ):
            raise ValueError("an active cooldown requires its remaining duration")


@dataclass(frozen=True, slots=True)
class AutomaticIrrigationResult:
    correlation_id: str
    recommendation: IrrigationRecommendation | None
    safety_decision: AutomaticSafetyDecision
    command_submitted: bool = False
    command_acknowledgement: CommandAcknowledgement | None = None

    def __post_init__(self) -> None:
        if not self.correlation_id.strip():
            raise ValueError("correlation_id must not be empty")
        if self.safety_decision.correlation_id != self.correlation_id:
            raise ValueError("safety decision correlation does not match the cycle")
        if self.command_submitted and not self.safety_decision.allowed:
            raise ValueError("a blocked cycle cannot submit a command")
        if self.command_acknowledgement is not None and not self.command_submitted:
            raise ValueError("a command acknowledgement requires a submitted command")
        if self.command_acknowledgement is not None and not self.safety_decision.allowed:
            raise ValueError("a blocked cycle cannot contain a command acknowledgement")
