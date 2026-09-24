"""Hardware-independent irrigation inference domain types."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

FEATURE_CONTRACT_VERSION = "v1"
MODEL_VERSION = "irrigation-baseline-v1"
METHODOLOGY_VERSION = "baseline-v1"
DATASET_SHA256 = (
    "F776F34FC9C7BE1EEF59614DC41DDEADEF6FDE9DC11D908C4EC8A513D6AF4D2D"  # pragma: allowlist secret
)
DECISION_THRESHOLD = 0.02040816326530612
ORDERED_FEATURES = (
    "soil_moisture_index_0_100",
    "air_temperature_c",
    "air_relative_humidity_percent",
)


class InferenceStatus(StrEnum):
    SUCCEEDED = "succeeded"
    INPUT_REJECTED = "input_rejected"
    MODEL_UNAVAILABLE = "model_unavailable"
    FAILED = "failed"


class InferenceReasonCode(StrEnum):
    MISSING_MEASUREMENT = "missing_measurement"
    INVALID_MEASUREMENT = "invalid_measurement"
    INVALID_MEASUREMENT_UNIT = "invalid_measurement_unit"
    INVALID_MEASUREMENT_QUALITY = "invalid_measurement_quality"
    STALE_SNAPSHOT = "stale_snapshot"
    FUTURE_OBSERVATION = "future_observation"
    MODEL_UNAVAILABLE = "model_unavailable"
    ARTIFACT_INTEGRITY_FAILED = "artifact_integrity_failed"
    MODEL_INCOMPATIBLE = "model_incompatible"
    INFERENCE_FAILED = "inference_failed"
    INVALID_MODEL_SCORE = "invalid_model_score"


@dataclass(frozen=True, slots=True)
class IrrigationFeatureVector:
    soil_moisture_index_0_100: float
    air_temperature_c: float
    air_relative_humidity_percent: float

    def __post_init__(self) -> None:
        values = self.as_ordered_tuple()
        if any(isinstance(value, bool) or not math.isfinite(value) for value in values):
            raise ValueError("inference features must be finite numbers")
        if not 0 <= self.soil_moisture_index_0_100 <= 100:
            raise ValueError("soil moisture feature must be between 0 and 100")
        if not 0 <= self.air_relative_humidity_percent <= 100:
            raise ValueError("air humidity feature must be between 0 and 100")

    def as_ordered_tuple(self) -> tuple[float, float, float]:
        """Return the immutable Feature Contract V1 order."""

        return (
            self.soil_moisture_index_0_100,
            self.air_temperature_c,
            self.air_relative_humidity_percent,
        )


@dataclass(frozen=True, slots=True)
class ModelPrediction:
    model_version: str
    feature_contract_version: str
    methodology_version: str
    score: float
    threshold: float


@dataclass(frozen=True, slots=True)
class IrrigationRecommendation:
    model_version: str
    feature_contract_version: str
    observed_at: datetime | None
    evaluated_at: datetime
    correlation_id: str
    score: float | None
    threshold: float
    irrigation_recommended: bool | None
    status: InferenceStatus
    reason_code: InferenceReasonCode | None = None

    def __post_init__(self) -> None:
        for field_name, value in (
            ("observed_at", self.observed_at),
            ("evaluated_at", self.evaluated_at),
        ):
            if value is not None and (
                value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value)
            ):
                raise ValueError(f"{field_name} must be UTC")
        if not self.correlation_id.strip():
            raise ValueError("correlation_id must not be empty")
        if not math.isfinite(self.threshold) or not 0 <= self.threshold <= 1:
            raise ValueError("threshold must be finite and between 0 and 1")
        if self.status is InferenceStatus.SUCCEEDED:
            if (
                self.observed_at is None
                or self.score is None
                or not math.isfinite(self.score)
                or not 0 <= self.score <= 1
                or self.irrigation_recommended is None
                or self.reason_code is not None
            ):
                raise ValueError("successful inference requires a valid decision")
        elif (
            self.score is not None
            or self.irrigation_recommended is not None
            or self.reason_code is None
        ):
            raise ValueError("unavailable inference must not contain a decision")
