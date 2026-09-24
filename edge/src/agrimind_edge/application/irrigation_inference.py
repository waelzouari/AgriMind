"""Validate sensor snapshots and request advisory irrigation inference."""

from __future__ import annotations

import logging
import math
from collections.abc import Callable, Iterable
from datetime import UTC, datetime

from agrimind_edge.application.inference_ports import (
    ArtifactIntegrityError,
    IrrigationModelPort,
    ModelCompatibilityError,
    ModelInferenceError,
    ModelUnavailableError,
)
from agrimind_edge.config.runtime import InferenceConfig
from agrimind_edge.domain.irrigation_inference import (
    DECISION_THRESHOLD,
    FEATURE_CONTRACT_VERSION,
    METHODOLOGY_VERSION,
    MODEL_VERSION,
    InferenceReasonCode,
    InferenceStatus,
    IrrigationFeatureVector,
    IrrigationRecommendation,
)
from agrimind_edge.domain.sensors import Measurement, ReadingQuality, SensorSnapshot


class IrrigationInferenceService:
    """Return a recommendation only; this service has no actuator dependency."""

    def __init__(
        self,
        model: IrrigationModelPort,
        config: InferenceConfig,
        *,
        clock: Callable[[], datetime] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._model = model
        self._config = config
        self._clock = clock or (lambda: datetime.now(UTC))
        self._logger = logger or logging.getLogger(__name__)

    def evaluate(self, snapshot: SensorSnapshot) -> IrrigationRecommendation:
        evaluated_at = self._now()
        measurements = (
            (snapshot.soil_humidity, "percent", True),
            (snapshot.temperature, "celsius", False),
            (snapshot.air_humidity, "percent", True),
        )
        reason = self._input_error(measurements, evaluated_at)
        observed_at = self._oldest_observation(measurement for measurement, _, _ in measurements)
        if reason is not None:
            return self._unavailable(
                snapshot,
                evaluated_at,
                observed_at,
                InferenceStatus.INPUT_REJECTED,
                reason,
            )

        values: list[float] = []
        for measurement, _, _ in measurements:
            value = measurement.value
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return self._unavailable(
                    snapshot,
                    evaluated_at,
                    observed_at,
                    InferenceStatus.INPUT_REJECTED,
                    InferenceReasonCode.INVALID_MEASUREMENT,
                )
            values.append(float(value))
        features = IrrigationFeatureVector(*values)
        try:
            prediction = self._model.predict(features)
        except ModelUnavailableError:
            return self._unavailable(
                snapshot,
                evaluated_at,
                observed_at,
                InferenceStatus.MODEL_UNAVAILABLE,
                InferenceReasonCode.MODEL_UNAVAILABLE,
            )
        except ArtifactIntegrityError:
            return self._unavailable(
                snapshot,
                evaluated_at,
                observed_at,
                InferenceStatus.MODEL_UNAVAILABLE,
                InferenceReasonCode.ARTIFACT_INTEGRITY_FAILED,
            )
        except ModelCompatibilityError:
            return self._unavailable(
                snapshot,
                evaluated_at,
                observed_at,
                InferenceStatus.MODEL_UNAVAILABLE,
                InferenceReasonCode.MODEL_INCOMPATIBLE,
            )
        except ModelInferenceError:
            return self._unavailable(
                snapshot,
                evaluated_at,
                observed_at,
                InferenceStatus.FAILED,
                InferenceReasonCode.INFERENCE_FAILED,
            )
        except Exception:
            return self._unavailable(
                snapshot,
                evaluated_at,
                observed_at,
                InferenceStatus.FAILED,
                InferenceReasonCode.INFERENCE_FAILED,
            )

        if (
            prediction.model_version != MODEL_VERSION
            or prediction.feature_contract_version != FEATURE_CONTRACT_VERSION
            or prediction.methodology_version != METHODOLOGY_VERSION
            or prediction.threshold != DECISION_THRESHOLD
        ):
            return self._unavailable(
                snapshot,
                evaluated_at,
                observed_at,
                InferenceStatus.MODEL_UNAVAILABLE,
                InferenceReasonCode.MODEL_INCOMPATIBLE,
            )
        if not math.isfinite(prediction.score) or not 0 <= prediction.score <= 1:
            return self._unavailable(
                snapshot,
                evaluated_at,
                observed_at,
                InferenceStatus.FAILED,
                InferenceReasonCode.INVALID_MODEL_SCORE,
            )
        recommendation = IrrigationRecommendation(
            model_version=prediction.model_version,
            feature_contract_version=prediction.feature_contract_version,
            observed_at=observed_at,
            evaluated_at=evaluated_at,
            correlation_id=snapshot.correlation_id,
            score=prediction.score,
            threshold=prediction.threshold,
            irrigation_recommended=prediction.score >= prediction.threshold,
            status=InferenceStatus.SUCCEEDED,
        )
        self._log(recommendation)
        return recommendation

    def _input_error(
        self,
        measurements: tuple[tuple[Measurement, str, bool], ...],
        evaluated_at: datetime,
    ) -> InferenceReasonCode | None:
        for measurement, unit, percentage in measurements:
            if measurement.quality is ReadingQuality.STALE:
                return InferenceReasonCode.STALE_SNAPSHOT
            if measurement.quality is not ReadingQuality.VALID:
                return InferenceReasonCode.INVALID_MEASUREMENT_QUALITY
            if measurement.value is None or measurement.observed_at is None:
                return InferenceReasonCode.MISSING_MEASUREMENT
            if measurement.unit != unit:
                return InferenceReasonCode.INVALID_MEASUREMENT_UNIT
            value = measurement.value
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return InferenceReasonCode.INVALID_MEASUREMENT
            numeric = float(value)
            if not math.isfinite(numeric) or (percentage and not 0 <= numeric <= 100):
                return InferenceReasonCode.INVALID_MEASUREMENT
            if measurement.observed_at > evaluated_at:
                return InferenceReasonCode.FUTURE_OBSERVATION
        observed_at = self._oldest_observation(measurement for measurement, _, _ in measurements)
        if observed_at is None:
            return InferenceReasonCode.MISSING_MEASUREMENT
        if (evaluated_at - observed_at).total_seconds() > self._config.max_age_seconds:
            return InferenceReasonCode.STALE_SNAPSHOT
        return None

    @staticmethod
    def _oldest_observation(measurements: Iterable[Measurement]) -> datetime | None:
        values = [
            measurement.observed_at
            for measurement in measurements
            if measurement.observed_at is not None
        ]
        return min(values) if values else None

    def _unavailable(
        self,
        snapshot: SensorSnapshot,
        evaluated_at: datetime,
        observed_at: datetime | None,
        status: InferenceStatus,
        reason: InferenceReasonCode,
    ) -> IrrigationRecommendation:
        recommendation = IrrigationRecommendation(
            model_version=MODEL_VERSION,
            feature_contract_version=FEATURE_CONTRACT_VERSION,
            observed_at=observed_at,
            evaluated_at=evaluated_at,
            correlation_id=snapshot.correlation_id,
            score=None,
            threshold=DECISION_THRESHOLD,
            irrigation_recommended=None,
            status=status,
            reason_code=reason,
        )
        self._log(recommendation)
        return recommendation

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() != UTC.utcoffset(now):
            raise ValueError("irrigation inference clock must return UTC")
        return now

    def _log(self, recommendation: IrrigationRecommendation) -> None:
        self._logger.info(
            "irrigation_inference_decision",
            extra={
                "event": "irrigation_inference_decision",
                "correlation_id": recommendation.correlation_id,
                "model_version": recommendation.model_version,
                "status": recommendation.status.value,
                "reason_code": (
                    recommendation.reason_code.value
                    if recommendation.reason_code is not None
                    else None
                ),
            },
        )
