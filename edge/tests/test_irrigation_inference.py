from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

import pytest

from agrimind_edge.application.inference_ports import (
    ArtifactIntegrityError,
    ModelCompatibilityError,
    ModelInferenceError,
    ModelUnavailableError,
)
from agrimind_edge.application.irrigation_inference import IrrigationInferenceService
from agrimind_edge.config import InferenceConfig
from agrimind_edge.domain import (
    DECISION_THRESHOLD,
    InferenceReasonCode,
    InferenceStatus,
    IrrigationFeatureVector,
    Measurement,
    ModelPrediction,
    ReadingQuality,
    SensorError,
    SensorErrorCode,
    SensorSnapshot,
)

NOW = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)


class FakeModel:
    def __init__(self, score: float = 0.94, error: Exception | None = None) -> None:
        self.score = score
        self.error = error
        self.seen: list[IrrigationFeatureVector] = []

    def predict(self, features: IrrigationFeatureVector) -> ModelPrediction:
        self.seen.append(features)
        if self.error is not None:
            raise self.error
        return ModelPrediction(
            model_version="irrigation-baseline-v1",
            feature_contract_version="v1",
            methodology_version="baseline-v1",
            score=self.score,
            threshold=DECISION_THRESHOLD,
        )


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
    temperature: Measurement | None = None,
    humidity: Measurement | None = None,
) -> SensorSnapshot:
    return SensorSnapshot(
        captured_at=NOW,
        correlation_id="corr-023",
        temperature=temperature or measurement(25.0, "celsius"),
        air_humidity=humidity or measurement(60.0, "percent"),
        soil_humidity=soil or measurement(45.0, "percent"),
        soil_raw=measurement(20_000.0, "adc_raw"),
        tank_distance=measurement(8.0, "centimeter"),
        tank_water_level=measurement(20.0, "centimeter"),
        tank_water_percent=measurement(66.0, "percent"),
    )


def service(model: FakeModel, *, now: datetime = NOW) -> IrrigationInferenceService:
    return IrrigationInferenceService(
        model,
        InferenceConfig(max_age_seconds=30),
        clock=lambda: now,
    )


def test_maps_snapshot_to_exact_v1_feature_order_and_ignores_system_state() -> None:
    model = FakeModel()

    result = service(model).evaluate(snapshot())

    assert model.seen[0].as_ordered_tuple() == (45.0, 25.0, 60.0)
    assert result.status is InferenceStatus.SUCCEEDED
    assert result.score == 0.94
    assert result.irrigation_recommended is True
    assert result.observed_at == NOW


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (math.nextafter(DECISION_THRESHOLD, 0.0), False),
        (DECISION_THRESHOLD, True),
        (math.nextafter(DECISION_THRESHOLD, 1.0), True),
    ],
)
def test_applies_approved_threshold_inclusively(score: float, expected: bool) -> None:
    result = service(FakeModel(score)).evaluate(snapshot())

    assert result.irrigation_recommended is expected


def test_uses_oldest_feature_observation_for_freshness() -> None:
    oldest = NOW - timedelta(seconds=31)
    model = FakeModel()
    result = service(model).evaluate(
        snapshot(soil=measurement(45.0, "percent", observed_at=oldest))
    )

    assert result.status is InferenceStatus.INPUT_REJECTED
    assert result.reason_code is InferenceReasonCode.STALE_SNAPSHOT
    assert result.observed_at == oldest
    assert result.score is None
    assert result.irrigation_recommended is None
    assert model.seen == []


@pytest.mark.parametrize(
    ("value", "unit", "reason"),
    [
        (math.nan, "percent", InferenceReasonCode.INVALID_MEASUREMENT),
        (math.inf, "percent", InferenceReasonCode.INVALID_MEASUREMENT),
        (-1.0, "percent", InferenceReasonCode.INVALID_MEASUREMENT),
        (101.0, "percent", InferenceReasonCode.INVALID_MEASUREMENT),
        (45.0, "fraction", InferenceReasonCode.INVALID_MEASUREMENT_UNIT),
    ],
)
def test_rejects_invalid_soil_measurement(
    value: float, unit: str, reason: InferenceReasonCode
) -> None:
    result = service(FakeModel()).evaluate(snapshot(soil=measurement(value, unit)))

    assert result.reason_code is reason
    assert result.irrigation_recommended is None


@pytest.mark.parametrize(
    ("quality", "reason"),
    [
        (ReadingQuality.STALE, InferenceReasonCode.STALE_SNAPSHOT),
        (ReadingQuality.UNAVAILABLE, InferenceReasonCode.INVALID_MEASUREMENT_QUALITY),
        (ReadingQuality.INVALID, InferenceReasonCode.INVALID_MEASUREMENT_QUALITY),
        (ReadingQuality.FAILED, InferenceReasonCode.INVALID_MEASUREMENT_QUALITY),
    ],
)
def test_rejects_non_valid_quality(quality: ReadingQuality, reason: InferenceReasonCode) -> None:
    value = 45.0 if quality is ReadingQuality.STALE else None
    observed_at = NOW if quality is ReadingQuality.STALE else None
    soil = measurement(value, "percent", quality=quality, observed_at=observed_at)

    result = service(FakeModel()).evaluate(snapshot(soil=soil))

    assert result.reason_code is reason
    assert result.score is None


def test_rejects_future_feature_observation() -> None:
    result = service(FakeModel()).evaluate(
        snapshot(humidity=measurement(60.0, "percent", observed_at=NOW + timedelta(microseconds=1)))
    )

    assert result.reason_code is InferenceReasonCode.FUTURE_OBSERVATION


@pytest.mark.parametrize(
    ("error", "status", "reason"),
    [
        (
            ModelUnavailableError(),
            InferenceStatus.MODEL_UNAVAILABLE,
            InferenceReasonCode.MODEL_UNAVAILABLE,
        ),
        (
            ArtifactIntegrityError(),
            InferenceStatus.MODEL_UNAVAILABLE,
            InferenceReasonCode.ARTIFACT_INTEGRITY_FAILED,
        ),
        (
            ModelCompatibilityError(),
            InferenceStatus.MODEL_UNAVAILABLE,
            InferenceReasonCode.MODEL_INCOMPATIBLE,
        ),
        (
            ModelInferenceError(),
            InferenceStatus.FAILED,
            InferenceReasonCode.INFERENCE_FAILED,
        ),
        (RuntimeError(), InferenceStatus.FAILED, InferenceReasonCode.INFERENCE_FAILED),
    ],
)
def test_model_failure_never_becomes_negative_recommendation(
    error: Exception,
    status: InferenceStatus,
    reason: InferenceReasonCode,
) -> None:
    result = service(FakeModel(error=error)).evaluate(snapshot())

    assert result.status is status
    assert result.reason_code is reason
    assert result.score is None
    assert result.irrigation_recommended is None


@pytest.mark.parametrize("score", [math.nan, math.inf, -0.1, 1.1])
def test_rejects_invalid_model_score(score: float) -> None:
    result = service(FakeModel(score)).evaluate(snapshot())

    assert result.status is InferenceStatus.FAILED
    assert result.reason_code is InferenceReasonCode.INVALID_MODEL_SCORE
    assert result.irrigation_recommended is None


def test_inference_is_deterministic() -> None:
    inference = service(FakeModel(0.94))

    first = inference.evaluate(snapshot())
    second = inference.evaluate(snapshot())

    assert first == second


def test_clock_must_be_utc() -> None:
    inference = IrrigationInferenceService(
        FakeModel(),
        InferenceConfig(),
        clock=lambda: datetime(2026, 9, 24, 12, 0),
    )

    with pytest.raises(ValueError, match="UTC"):
        inference.evaluate(snapshot())
