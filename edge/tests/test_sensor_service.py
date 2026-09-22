from __future__ import annotations

import logging
import math
from datetime import UTC, datetime, timedelta

import pytest

from agrimind_edge.adapters.fake import FakeAirSensor, FakeSoilSensor, FakeTankSensor
from agrimind_edge.application import SensorService
from agrimind_edge.domain import ReadingQuality, SensorErrorCode

NOW = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)


def air(
    temperature: float | None = 24.5,
    humidity: float | None = 62.0,
    error: str | None = None,
) -> dict[str, float | str | None]:
    return {"temperature": temperature, "humidity_air": humidity, "error": error}


def soil(
    humidity: float | None = 45.0,
    raw: int | None = 20_350,
    error: str | None = None,
) -> dict[str, float | int | str | None]:
    return {"soil_humidity": humidity, "soil_raw": raw, "error": error}


def tank(
    distance: float = 8.0,
    water_level: float = 20.0,
    water_percent: float = 66.7,
    error: str | None = None,
) -> dict[str, float | str | None]:
    return {
        "distance_cm": distance,
        "water_level_cm": water_level,
        "water_pct": water_percent,
        "error": error,
    }


def service(
    air_steps: list[object],
    soil_steps: list[object],
    tank_steps: list[object],
    *,
    times: list[datetime] | None = None,
    logger: logging.Logger | None = None,
) -> SensorService:
    clock_values = iter(times or [NOW])
    return SensorService(
        FakeAirSensor(air_steps),  # type: ignore[arg-type]
        FakeSoilSensor(soil_steps),  # type: ignore[arg-type]
        FakeTankSensor(tank_steps),  # type: ignore[arg-type]
        clock=lambda: next(clock_values),
        correlation_id_factory=lambda: "corr-004",
        logger=logger,
    )


def test_successful_snapshot_is_typed_utc_and_internal() -> None:
    snapshot = service([air()], [soil()], [tank()]).capture()

    assert snapshot.captured_at == NOW
    assert snapshot.correlation_id == "corr-004"
    assert snapshot.temperature.value == 24.5
    assert snapshot.temperature.unit == "celsius"
    assert snapshot.soil_raw.value == 20_350
    assert snapshot.tank_water_percent.value == 66.7
    assert snapshot.temperature.quality is ReadingQuality.VALID
    assert snapshot.temperature.observed_at == NOW
    assert snapshot.degraded is False
    assert not hasattr(snapshot, "farm_id")
    assert not hasattr(snapshot, "schema_version")


def test_unavailable_sensor_does_not_discard_healthy_readings() -> None:
    snapshot = service(
        [air(error="device missing")],
        [soil()],
        [tank()],
    ).capture()

    assert snapshot.temperature.value is None
    assert snapshot.temperature.quality is ReadingQuality.UNAVAILABLE
    assert snapshot.temperature.error is not None
    assert snapshot.temperature.error.code is SensorErrorCode.SENSOR_UNAVAILABLE
    assert snapshot.soil_humidity.value == 45.0
    assert snapshot.soil_humidity.quality is ReadingQuality.VALID
    assert snapshot.tank_distance.value == 8.0
    assert snapshot.degraded is True


def test_unexpected_failure_isolated_from_other_sensors() -> None:
    snapshot = service(
        [RuntimeError("private device detail")],
        [soil()],
        [tank()],
    ).capture()

    assert snapshot.temperature.quality is ReadingQuality.FAILED
    assert snapshot.temperature.error is not None
    assert snapshot.temperature.error.code is SensorErrorCode.READ_FAILED
    assert snapshot.temperature.error.message == "sensor read failed"
    assert snapshot.soil_humidity.quality is ReadingQuality.VALID


@pytest.mark.parametrize("bad_value", [None, math.nan, math.inf, -1.0, 101.0, True])
def test_invalid_percentage_is_explicit(bad_value: object) -> None:
    snapshot = service(
        [air()],
        [soil(humidity=bad_value)],  # type: ignore[arg-type]
        [tank()],
    ).capture()

    assert snapshot.soil_humidity.quality is ReadingQuality.INVALID
    assert snapshot.soil_humidity.value is None
    assert snapshot.soil_raw.quality is ReadingQuality.VALID


def test_last_good_value_becomes_stale_then_recovers(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("agrimind.test.sensor-recovery")
    caplog.set_level(logging.INFO, logger=logger.name)
    sensor_service = service(
        [air(), air(error="offline"), air(25.0, 60.0)],
        [soil(), soil(), soil()],
        [tank(), tank(), tank()],
        times=[NOW, NOW + timedelta(minutes=1), NOW + timedelta(minutes=2)],
        logger=logger,
    )

    first = sensor_service.capture()
    second = sensor_service.capture()
    third = sensor_service.capture()

    assert second.temperature.value == first.temperature.value
    assert second.temperature.quality is ReadingQuality.STALE
    assert second.temperature.observed_at == NOW
    assert second.temperature.error is not None
    assert second.temperature.error.code is SensorErrorCode.SENSOR_UNAVAILABLE
    assert third.temperature.value == 25.0
    assert third.temperature.quality is ReadingQuality.VALID
    assert third.temperature.observed_at == NOW + timedelta(minutes=2)
    assert [record.message for record in caplog.records] == [
        "sensor_read_degraded",
        "sensor_recovered",
    ]
    assert caplog.records[0].correlation_id == "corr-004"  # type: ignore[attr-defined]
    assert caplog.records[0].sensor == "air"  # type: ignore[attr-defined]
    assert "offline" not in caplog.text


def test_clock_and_correlation_id_must_be_valid() -> None:
    naive = SensorService(
        FakeAirSensor([air()]),
        FakeSoilSensor([soil()]),
        FakeTankSensor([tank()]),
        clock=lambda: datetime(2026, 9, 22),
    )
    with pytest.raises(ValueError, match="UTC"):
        naive.capture()

    blank_id = SensorService(
        FakeAirSensor([air()]),
        FakeSoilSensor([soil()]),
        FakeTankSensor([tank()]),
        clock=lambda: NOW,
        correlation_id_factory=lambda: " ",
    )
    with pytest.raises(ValueError, match="empty"):
        blank_id.capture()
