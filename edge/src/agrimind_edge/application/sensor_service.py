"""Collect independent sensor readings into a resilient internal snapshot."""

from __future__ import annotations

import logging
import math
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TypeAlias
from uuid import uuid4

from agrimind_edge.application.ports import AirSensorPort, SoilSensorPort, TankSensorPort
from agrimind_edge.domain.sensors import (
    Measurement,
    ReadingQuality,
    SensorError,
    SensorErrorCode,
    SensorSnapshot,
)

_Metric: TypeAlias = tuple[str, str]
_AIR_METRICS: tuple[_Metric, ...] = (("temperature", "celsius"), ("humidity_air", "percent"))
_SOIL_METRICS: tuple[_Metric, ...] = (("soil_humidity", "percent"), ("soil_raw", "adc_raw"))
_TANK_METRICS: tuple[_Metric, ...] = (
    ("distance_cm", "centimeter"),
    ("water_level_cm", "centimeter"),
    ("water_pct", "percent"),
)


class SensorService:
    """Read every sensor independently and retain last-known values on failure."""

    def __init__(
        self,
        air_sensor: AirSensorPort,
        soil_sensor: SoilSensorPort,
        tank_sensor: TankSensorPort,
        *,
        clock: Callable[[], datetime] | None = None,
        correlation_id_factory: Callable[[], str] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._air_sensor = air_sensor
        self._soil_sensor = soil_sensor
        self._tank_sensor = tank_sensor
        self._clock = clock or (lambda: datetime.now(UTC))
        self._correlation_id_factory = correlation_id_factory or (lambda: str(uuid4()))
        self._logger = logger or logging.getLogger(__name__)
        self._last_valid: dict[str, Measurement] = {}
        self._degraded_sensors: set[str] = set()

    def capture(self) -> SensorSnapshot:
        captured_at = self._clock()
        if captured_at.tzinfo is None or captured_at.utcoffset() != UTC.utcoffset(captured_at):
            raise ValueError("sensor service clock must return UTC")
        correlation_id = self._correlation_id_factory()
        if not correlation_id.strip():
            raise ValueError("correlation ID factory returned an empty value")

        air = self._read_sensor(
            "air", _AIR_METRICS, self._air_sensor.read, captured_at, correlation_id
        )
        soil = self._read_sensor(
            "soil", _SOIL_METRICS, self._soil_sensor.read, captured_at, correlation_id
        )
        tank = self._read_sensor(
            "tank", _TANK_METRICS, self._tank_sensor.read, captured_at, correlation_id
        )
        return SensorSnapshot(
            captured_at=captured_at,
            correlation_id=correlation_id,
            temperature=air["temperature"],
            air_humidity=air["humidity_air"],
            soil_humidity=soil["soil_humidity"],
            soil_raw=soil["soil_raw"],
            tank_distance=tank["distance_cm"],
            tank_water_level=tank["water_level_cm"],
            tank_water_percent=tank["water_pct"],
        )

    def _read_sensor(
        self,
        sensor: str,
        metrics: tuple[_Metric, ...],
        read: Callable[[], object],
        captured_at: datetime,
        correlation_id: str,
    ) -> dict[str, Measurement]:
        try:
            raw = read()
        except Exception:  # isolate third-party and device-specific failures
            return self._degraded(
                sensor,
                metrics,
                SensorError(SensorErrorCode.READ_FAILED, "sensor read failed"),
                correlation_id,
            )

        if not isinstance(raw, dict):
            return self._degraded(
                sensor,
                metrics,
                SensorError(SensorErrorCode.INVALID_READING, "sensor returned an invalid result"),
                correlation_id,
            )
        if raw.get("error"):
            return self._degraded(
                sensor,
                metrics,
                SensorError(SensorErrorCode.SENSOR_UNAVAILABLE, "sensor is unavailable"),
                correlation_id,
            )

        readings: dict[str, Measurement] = {}
        has_invalid = False
        for name, unit in metrics:
            value = raw.get(name)
            if not self._is_valid_value(name, value):
                has_invalid = True
                readings[name] = self._fallback(
                    name,
                    unit,
                    SensorError(
                        SensorErrorCode.INVALID_READING,
                        "sensor returned an invalid value",
                    ),
                )
                continue
            measurement = Measurement(
                value=value,
                unit=unit,
                quality=ReadingQuality.VALID,
                observed_at=captured_at,
            )
            self._last_valid[name] = measurement
            readings[name] = measurement

        if has_invalid:
            self._mark_degraded(sensor, SensorErrorCode.INVALID_READING, correlation_id)
        else:
            self._mark_recovered(sensor, correlation_id)
        return readings

    @staticmethod
    def _is_valid_value(name: str, value: object) -> bool:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return False
        if not math.isfinite(float(value)):
            return False
        if name in {"humidity_air", "soil_humidity", "water_pct"}:
            return 0 <= value <= 100
        if name in {"soil_raw", "distance_cm", "water_level_cm"}:
            return value >= 0
        return True

    def _degraded(
        self,
        sensor: str,
        metrics: tuple[_Metric, ...],
        error: SensorError,
        correlation_id: str,
    ) -> dict[str, Measurement]:
        self._mark_degraded(sensor, error.code, correlation_id)
        return {name: self._fallback(name, unit, error) for name, unit in metrics}

    def _fallback(self, name: str, unit: str, error: SensorError) -> Measurement:
        cached = self._last_valid.get(name)
        if cached is not None:
            return Measurement(
                value=cached.value,
                unit=unit,
                quality=ReadingQuality.STALE,
                observed_at=cached.observed_at,
                error=error,
            )
        quality = {
            SensorErrorCode.SENSOR_UNAVAILABLE: ReadingQuality.UNAVAILABLE,
            SensorErrorCode.INVALID_READING: ReadingQuality.INVALID,
            SensorErrorCode.READ_FAILED: ReadingQuality.FAILED,
        }[error.code]
        return Measurement(value=None, unit=unit, quality=quality, observed_at=None, error=error)

    def _mark_degraded(self, sensor: str, error_code: SensorErrorCode, correlation_id: str) -> None:
        self._degraded_sensors.add(sensor)
        self._logger.warning(
            "sensor_read_degraded",
            extra={
                "event": "sensor_read_degraded",
                "sensor": sensor,
                "error_code": error_code.value,
                "correlation_id": correlation_id,
            },
        )

    def _mark_recovered(self, sensor: str, correlation_id: str) -> None:
        if sensor not in self._degraded_sensors:
            return
        self._degraded_sensors.remove(sensor)
        self._logger.info(
            "sensor_recovered",
            extra={
                "event": "sensor_recovered",
                "sensor": sensor,
                "correlation_id": correlation_id,
            },
        )
