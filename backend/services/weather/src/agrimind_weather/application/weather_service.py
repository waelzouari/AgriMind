"""Farm-isolated cache and refresh policy for weather snapshots."""

from __future__ import annotations

import logging
from datetime import timedelta
from uuid import UUID

from agrimind_weather.application.aggregation import aggregate_weather
from agrimind_weather.application.ports import (
    Clock,
    FarmLocationRepository,
    WeatherProvider,
    WeatherStore,
)
from agrimind_weather.domain import (
    WeatherError,
    WeatherFailure,
    WeatherFreshness,
    WeatherResult,
    WeatherSnapshot,
)

LOGGER = logging.getLogger(__name__)


class WeatherService:
    def __init__(
        self,
        locations: FarmLocationRepository,
        provider: WeatherProvider,
        store: WeatherStore,
        clock: Clock,
        *,
        fresh_ttl: timedelta,
        maximum_stale_age: timedelta,
    ) -> None:
        if fresh_ttl <= timedelta(0):
            raise ValueError("fresh TTL must be positive")
        if maximum_stale_age <= fresh_ttl:
            raise ValueError("maximum stale age must exceed fresh TTL")
        self._locations = locations
        self._provider = provider
        self._store = store
        self._clock = clock
        self._fresh_ttl = fresh_ttl
        self._maximum_stale_age = maximum_stale_age

    def refresh(self, farm_id: UUID) -> WeatherResult:
        now = self._clock.now()
        if now.tzinfo is None or now.utcoffset() != timedelta(0):
            raise ValueError("weather clock must return timezone-aware UTC")
        try:
            location = self._locations.get_location(farm_id)
        except WeatherError as error:
            return WeatherResult(WeatherFreshness.UNAVAILABLE, failure=error.failure)
        if location is None:
            LOGGER.info(
                "weather.location.missing",
                extra={"event": "weather.location.missing", "farm_id": str(farm_id)},
            )
            return WeatherResult(
                WeatherFreshness.UNAVAILABLE,
                failure=WeatherFailure.LOCATION_NOT_CONFIGURED,
            )

        try:
            cached = self._store.get(farm_id)
        except WeatherError:
            cached = None
        same_location = cached is not None and cached.location == location
        if cached is not None and same_location and now <= cached.fresh_until:
            LOGGER.info(
                "weather.cache.hit", extra={"event": "weather.cache.hit", "farm_id": str(farm_id)}
            )
            return WeatherResult(WeatherFreshness.FRESH, snapshot=cached)

        stale_fallback = same_location and cached is not None and now <= cached.stale_until
        if stale_fallback:
            LOGGER.info(
                "weather.cache.stale",
                extra={"event": "weather.cache.stale", "farm_id": str(farm_id)},
            )
        LOGGER.info(
            "weather.refresh.started",
            extra={"event": "weather.refresh.started", "farm_id": str(farm_id)},
        )
        try:
            provider_weather = self._provider.fetch(location)
            LOGGER.info(
                "weather.provider.success",
                extra={"event": "weather.provider.success", "farm_id": str(farm_id)},
            )
            snapshot = WeatherSnapshot(
                farm_id=farm_id,
                provider="open-meteo",
                location=location,
                current=provider_weather.current,
                aggregates=aggregate_weather(provider_weather),
                fetched_at=now,
                fresh_until=now + self._fresh_ttl,
                stale_until=now + self._maximum_stale_age,
            )
            self._store.upsert(snapshot)
        except (WeatherError, ValueError) as error:
            failure = (
                error.failure
                if isinstance(error, WeatherError)
                else WeatherFailure.INVALID_PROVIDER_PAYLOAD
            )
            LOGGER.warning(
                "weather.provider.failure",
                extra={
                    "event": "weather.provider.failure",
                    "farm_id": str(farm_id),
                    "reason_code": failure.value,
                },
            )
            if stale_fallback:
                LOGGER.info(
                    "weather.cache.fallback",
                    extra={"event": "weather.cache.fallback", "farm_id": str(farm_id)},
                )
                return WeatherResult(WeatherFreshness.STALE, snapshot=cached, failure=failure)
            return WeatherResult(WeatherFreshness.UNAVAILABLE, failure=failure)

        LOGGER.info(
            "weather.snapshot.updated",
            extra={"event": "weather.snapshot.updated", "farm_id": str(farm_id)},
        )
        return WeatherResult(WeatherFreshness.FRESH, snapshot=snapshot)
