"""Typed sensor readings and snapshots independent of transport and GPIO."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import TypedDict


class AirReading(TypedDict):
    temperature: float | None
    humidity_air: float | None
    error: str | None


class SoilReading(TypedDict):
    soil_humidity: float | None
    soil_raw: int | None
    error: str | None


class TankReading(TypedDict):
    distance_cm: float
    water_level_cm: float
    water_pct: float
    error: str | None


class PumpResult(TypedDict):
    pump: bool
    message: str


class ReadingQuality(StrEnum):
    VALID = "valid"
    STALE = "stale"
    UNAVAILABLE = "unavailable"
    INVALID = "invalid"
    FAILED = "failed"


class SensorErrorCode(StrEnum):
    SENSOR_UNAVAILABLE = "sensor_unavailable"
    INVALID_READING = "invalid_reading"
    READ_FAILED = "read_failed"


@dataclass(frozen=True, slots=True)
class SensorError:
    code: SensorErrorCode
    message: str

    def __post_init__(self) -> None:
        if not self.message.strip():
            raise ValueError("sensor error message must not be empty")


@dataclass(frozen=True, slots=True)
class Measurement:
    """One typed value, including freshness and failure state."""

    value: float | int | None
    unit: str
    quality: ReadingQuality
    observed_at: datetime | None
    error: SensorError | None = None

    def __post_init__(self) -> None:
        if not self.unit:
            raise ValueError("measurement unit must not be empty")
        if self.observed_at is not None and (
            self.observed_at.tzinfo is None
            or self.observed_at.utcoffset() != UTC.utcoffset(self.observed_at)
        ):
            raise ValueError("observed_at must be UTC")
        if self.quality is ReadingQuality.VALID:
            if self.value is None or self.observed_at is None or self.error is not None:
                raise ValueError("valid measurements require a value/time and no error")
        elif self.quality is ReadingQuality.STALE:
            if self.value is None or self.observed_at is None or self.error is None:
                raise ValueError("stale measurements require cached value/time and an error")
        elif self.value is not None or self.observed_at is not None or self.error is None:
            raise ValueError("failed measurements require only error information")


@dataclass(frozen=True, slots=True)
class SensorSnapshot:
    """Internal service result; conversion to a wire contract happens later."""

    captured_at: datetime
    correlation_id: str
    temperature: Measurement
    air_humidity: Measurement
    soil_humidity: Measurement
    soil_raw: Measurement
    tank_distance: Measurement
    tank_water_level: Measurement
    tank_water_percent: Measurement

    def __post_init__(self) -> None:
        if not self.correlation_id.strip():
            raise ValueError("correlation_id must not be empty")
        if self.captured_at.tzinfo is None or self.captured_at.utcoffset() != UTC.utcoffset(
            self.captured_at
        ):
            raise ValueError("captured_at must be UTC")

    @property
    def degraded(self) -> bool:
        return any(
            measurement.quality is not ReadingQuality.VALID
            for measurement in (
                self.temperature,
                self.air_humidity,
                self.soil_humidity,
                self.soil_raw,
                self.tank_distance,
                self.tank_water_level,
                self.tank_water_percent,
            )
        )
