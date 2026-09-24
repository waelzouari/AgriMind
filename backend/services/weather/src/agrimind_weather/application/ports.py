"""Mockable boundaries used by the weather application service."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from agrimind_weather.domain import FarmLocation, ProviderWeather, WeatherSnapshot


class Clock(Protocol):
    def now(self) -> datetime: ...


class WeatherProvider(Protocol):
    def fetch(self, location: FarmLocation) -> ProviderWeather: ...


class WeatherStore(Protocol):
    def get(self, farm_id: UUID) -> WeatherSnapshot | None: ...

    def upsert(self, snapshot: WeatherSnapshot) -> None: ...


class FarmLocationRepository(Protocol):
    def get_location(self, farm_id: UUID) -> FarmLocation | None: ...

    def list_located_farm_ids(self) -> tuple[UUID, ...]: ...
