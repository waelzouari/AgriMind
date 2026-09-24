from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from agrimind_weather.domain import (
    FarmLocation,
    HourlyWeather,
    ProviderWeather,
    WeatherCurrent,
    WeatherError,
    WeatherSnapshot,
)

NOW = datetime(2026, 9, 23, 12, 30, tzinfo=UTC)
FARM = UUID("19191919-1919-4919-8919-191919191901")
OTHER_FARM = UUID("19191919-1919-4919-8919-191919191902")
LOCATION = FarmLocation(36.8065, 10.1815)


class FixedClock:
    def __init__(self, value: datetime = NOW) -> None:
        self.value = value

    def now(self) -> datetime:
        return self.value


def provider_weather(*, rain: float = 1, et0: float = 0.25) -> ProviderWeather:
    start = datetime(2026, 9, 21, 12, tzinfo=UTC)
    return ProviderWeather(
        current=WeatherCurrent(
            source_time=datetime(2026, 9, 23, 12, tzinfo=UTC),
            temperature_c=25,
            relative_humidity_percent=60,
            precipitation_mm=0.1,
            interval_seconds=900,
            weather_code=2,
            wind_speed_kmh=12,
        ),
        hourly=tuple(
            HourlyWeather(start + timedelta(hours=index), rain, et0) for index in range(49)
        ),
    )


class FakeLocations:
    def __init__(self, location: FarmLocation | None = LOCATION) -> None:
        self.location = location
        self.farm_ids: tuple[UUID, ...] = (FARM,)
        self.error: WeatherError | None = None

    def get_location(self, farm_id: UUID) -> FarmLocation | None:
        del farm_id
        if self.error:
            raise self.error
        return self.location

    def list_located_farm_ids(self) -> tuple[UUID, ...]:
        if self.error:
            raise self.error
        return self.farm_ids


class FakeProvider:
    def __init__(self) -> None:
        self.value = provider_weather()
        self.error: WeatherError | None = None
        self.calls = 0

    def fetch(self, location: FarmLocation) -> ProviderWeather:
        del location
        self.calls += 1
        if self.error:
            raise self.error
        return self.value


class FakeStore:
    def __init__(self, snapshot: WeatherSnapshot | None = None) -> None:
        self.snapshot = snapshot
        self.upserts = 0
        self.error: WeatherError | None = None

    def get(self, farm_id: UUID) -> WeatherSnapshot | None:
        del farm_id
        if self.error:
            raise self.error
        return self.snapshot

    def upsert(self, snapshot: WeatherSnapshot) -> None:
        if self.error:
            raise self.error
        self.snapshot = snapshot
        self.upserts += 1
