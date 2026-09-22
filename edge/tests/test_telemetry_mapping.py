from __future__ import annotations

from datetime import UTC, datetime
from itertools import count
from uuid import UUID

from agrimind_edge.application import TelemetryMapper
from agrimind_edge.contracts.enums import TelemetryMetric, TelemetryQuality
from agrimind_edge.contracts.models import Telemetry
from agrimind_edge.domain import (
    Measurement,
    ReadingQuality,
    SensorError,
    SensorErrorCode,
    SensorSnapshot,
)

NOW = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)
FARM_ID = UUID("11111111-1111-4111-8111-111111111111")
DEVICE_ID = UUID("22222222-2222-4222-8222-222222222222")


def valid(value: float | int, unit: str) -> Measurement:
    return Measurement(value, unit, ReadingQuality.VALID, NOW)


def snapshot(*, soil: Measurement | None = None) -> SensorSnapshot:
    return SensorSnapshot(
        captured_at=NOW,
        correlation_id="snapshot-006",
        temperature=valid(24.5, "celsius"),
        air_humidity=valid(62.0, "percent"),
        soil_humidity=soil or valid(45.0, "percent"),
        soil_raw=valid(20_350, "adc_raw"),
        tank_distance=valid(8.0, "centimeter"),
        tank_water_level=valid(20.0, "centimeter"),
        tank_water_percent=valid(66.7, "percent"),
    )


def mapper() -> TelemetryMapper:
    identifiers = count(100)
    return TelemetryMapper(
        FARM_ID,
        DEVICE_ID,
        message_id_factory=lambda: UUID(int=next(identifiers)),
    )


def test_maps_four_approved_measurements_with_contract_units() -> None:
    result = mapper().map_snapshot(snapshot())

    assert result.skipped_unavailable == 0
    assert [item.metric for item in result.telemetry] == [
        TelemetryMetric.TEMPERATURE,
        TelemetryMetric.HUMIDITY,
        TelemetryMetric.SOIL_MOISTURE,
        TelemetryMetric.TANK_LEVEL,
    ]
    assert [item.value for item in result.telemetry] == [24.5, 62.0, 45.0, 20.0]
    assert [item.unit for item in result.telemetry] == ["°C", "%", "%", "cm"]
    assert all(item.farm_id == FARM_ID for item in result.telemetry)
    assert all(item.device_id == DEVICE_ID for item in result.telemetry)
    assert all(item.recorded_at == NOW for item in result.telemetry)
    assert all(item.quality is TelemetryQuality.VALID for item in result.telemetry)
    assert Telemetry.from_json(result.telemetry[0].to_json()) == result.telemetry[0]


def test_stale_value_maps_to_estimated_with_original_observation_time() -> None:
    stale_time = datetime(2026, 9, 22, 11, 55, tzinfo=UTC)
    stale = Measurement(
        42.0,
        "percent",
        ReadingQuality.STALE,
        stale_time,
        SensorError(SensorErrorCode.SENSOR_UNAVAILABLE, "sensor is unavailable"),
    )

    result = mapper().map_snapshot(snapshot(soil=stale))
    mapped = next(item for item in result.telemetry if item.metric is TelemetryMetric.SOIL_MOISTURE)

    assert mapped.quality is TelemetryQuality.ESTIMATED
    assert mapped.recorded_at == stale_time
    assert mapped.value == 42.0


def test_unavailable_value_is_omitted_instead_of_fabricated() -> None:
    unavailable = Measurement(
        None,
        "percent",
        ReadingQuality.UNAVAILABLE,
        None,
        SensorError(SensorErrorCode.SENSOR_UNAVAILABLE, "sensor is unavailable"),
    )

    result = mapper().map_snapshot(snapshot(soil=unavailable))

    assert result.skipped_unavailable == 1
    assert all(item.metric is not TelemetryMetric.SOIL_MOISTURE for item in result.telemetry)
