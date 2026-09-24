"""Provider-independent weather values and safe failure categories."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID


class WeatherFreshness(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    UNAVAILABLE = "unavailable"


class WeatherFailure(StrEnum):
    LOCATION_NOT_CONFIGURED = "location_not_configured"
    INVALID_LOCATION = "invalid_location"
    NETWORK = "network"
    TIMEOUT = "timeout"
    PROVIDER_HTTP_ERROR = "provider_http_error"
    INVALID_PROVIDER_PAYLOAD = "invalid_provider_payload"
    CACHE_UNAVAILABLE = "cache_unavailable"
    STORAGE_ERROR = "storage_error"


class WeatherError(RuntimeError):
    def __init__(self, failure: WeatherFailure) -> None:
        super().__init__(failure.value)
        self.failure = failure


def _utc(value: datetime, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
        raise ValueError(f"{field} must be timezone-aware UTC")


def _finite(value: float, field: str) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{field} must be finite")


@dataclass(frozen=True, slots=True)
class FarmLocation:
    latitude: float
    longitude: float

    def __post_init__(self) -> None:
        _finite(self.latitude, "latitude")
        _finite(self.longitude, "longitude")
        if not -90 <= self.latitude <= 90:
            raise ValueError("latitude must be between -90 and 90")
        if not -180 <= self.longitude <= 180:
            raise ValueError("longitude must be between -180 and 180")


@dataclass(frozen=True, slots=True)
class WeatherCurrent:
    source_time: datetime
    temperature_c: float
    relative_humidity_percent: float
    precipitation_mm: float
    interval_seconds: int
    weather_code: int
    wind_speed_kmh: float

    def __post_init__(self) -> None:
        _utc(self.source_time, "source_time")
        for field, value in (
            ("temperature_c", self.temperature_c),
            ("relative_humidity_percent", self.relative_humidity_percent),
            ("precipitation_mm", self.precipitation_mm),
            ("wind_speed_kmh", self.wind_speed_kmh),
        ):
            _finite(value, field)
        if not 0 <= self.relative_humidity_percent <= 100:
            raise ValueError("relative humidity must be between 0 and 100")
        if self.precipitation_mm < 0 or self.wind_speed_kmh < 0:
            raise ValueError("precipitation and wind speed must not be negative")
        if self.interval_seconds <= 0:
            raise ValueError("current interval must be positive")


@dataclass(frozen=True, slots=True)
class HourlyWeather:
    time: datetime
    precipitation_mm: float
    et0_mm: float

    def __post_init__(self) -> None:
        _utc(self.time, "hourly time")
        _finite(self.precipitation_mm, "hourly precipitation")
        _finite(self.et0_mm, "hourly ET0")
        if self.precipitation_mm < 0 or self.et0_mm < 0:
            raise ValueError("hourly precipitation and ET0 must not be negative")


@dataclass(frozen=True, slots=True)
class ProviderWeather:
    current: WeatherCurrent
    hourly: tuple[HourlyWeather, ...]


@dataclass(frozen=True, slots=True)
class WeatherAggregates:
    precipitation_last_6h_mm: float
    precipitation_last_12h_mm: float
    precipitation_last_24h_mm: float
    precipitation_previous_24h_mm: float
    et0_last_24h_mm: float

    def __post_init__(self) -> None:
        for field, value in (
            ("precipitation_last_6h_mm", self.precipitation_last_6h_mm),
            ("precipitation_last_12h_mm", self.precipitation_last_12h_mm),
            ("precipitation_last_24h_mm", self.precipitation_last_24h_mm),
            ("precipitation_previous_24h_mm", self.precipitation_previous_24h_mm),
            ("et0_last_24h_mm", self.et0_last_24h_mm),
        ):
            _finite(value, field)
            if value < 0:
                raise ValueError(f"{field} must not be negative")


@dataclass(frozen=True, slots=True)
class WeatherSnapshot:
    farm_id: UUID
    provider: str
    location: FarmLocation
    current: WeatherCurrent
    aggregates: WeatherAggregates
    fetched_at: datetime
    fresh_until: datetime
    stale_until: datetime

    def __post_init__(self) -> None:
        _utc(self.fetched_at, "fetched_at")
        _utc(self.fresh_until, "fresh_until")
        _utc(self.stale_until, "stale_until")
        if not self.fetched_at <= self.fresh_until < self.stale_until:
            raise ValueError("snapshot freshness timestamps are inconsistent")


@dataclass(frozen=True, slots=True)
class WeatherResult:
    freshness: WeatherFreshness
    snapshot: WeatherSnapshot | None = None
    failure: WeatherFailure | None = None

    def __post_init__(self) -> None:
        if self.freshness is WeatherFreshness.UNAVAILABLE and self.snapshot is not None:
            raise ValueError("unavailable weather cannot include a snapshot")
        if self.freshness is not WeatherFreshness.UNAVAILABLE and self.snapshot is None:
            raise ValueError("usable weather must include a snapshot")
