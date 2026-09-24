from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest
from fakes import FARM, FakeLocations, FakeProvider, FakeStore, FixedClock

from agrimind_weather.application.weather_service import WeatherService
from agrimind_weather.domain import (
    FarmLocation,
    WeatherError,
    WeatherFailure,
    WeatherFreshness,
    WeatherSnapshot,
)


def service(
    locations: FakeLocations,
    provider: FakeProvider,
    store: FakeStore,
    clock: FixedClock,
) -> WeatherService:
    return WeatherService(
        locations,
        provider,
        store,
        clock,
        fresh_ttl=timedelta(minutes=30),
        maximum_stale_age=timedelta(hours=6),
    )


def fetched_snapshot(
    clock: FixedClock, provider: FakeProvider, store: FakeStore
) -> WeatherSnapshot:
    result = service(FakeLocations(), provider, store, clock).refresh(FARM)
    assert result.snapshot is not None
    return result.snapshot


def test_missing_location_never_calls_provider() -> None:
    locations = FakeLocations(None)
    provider = FakeProvider()
    result = service(locations, provider, FakeStore(), FixedClock()).refresh(FARM)

    assert result.freshness is WeatherFreshness.UNAVAILABLE
    assert result.failure is WeatherFailure.LOCATION_NOT_CONFIGURED
    assert provider.calls == 0


@pytest.mark.parametrize(
    ("offset", "expected"),
    [
        (timedelta(minutes=29, seconds=59), WeatherFreshness.FRESH),
        (timedelta(minutes=30), WeatherFreshness.FRESH),
    ],
)
def test_fresh_cache_boundaries_skip_provider(
    offset: timedelta, expected: WeatherFreshness
) -> None:
    initial_clock = FixedClock()
    provider = FakeProvider()
    snapshot = fetched_snapshot(initial_clock, provider, FakeStore())
    provider.calls = 0
    clock = FixedClock(initial_clock.value + offset)

    result = service(FakeLocations(), provider, FakeStore(snapshot), clock).refresh(FARM)

    assert result.freshness is expected
    assert provider.calls == 0


def test_stale_cache_refresh_success_replaces_snapshot() -> None:
    clock = FixedClock()
    provider = FakeProvider()
    snapshot = fetched_snapshot(clock, provider, FakeStore())
    provider.calls = 0
    store = FakeStore(snapshot)
    clock.value += timedelta(minutes=30, microseconds=1)

    result = service(FakeLocations(), provider, store, clock).refresh(FARM)

    assert result.freshness is WeatherFreshness.FRESH
    assert provider.calls == 1
    assert store.upserts == 1
    assert result.snapshot is not snapshot


@pytest.mark.parametrize(
    ("offset", "expected"),
    [
        (timedelta(minutes=30, microseconds=1), WeatherFreshness.STALE),
        (timedelta(hours=6), WeatherFreshness.STALE),
        (timedelta(hours=6, microseconds=1), WeatherFreshness.UNAVAILABLE),
    ],
)
def test_provider_failure_respects_maximum_stale_boundary(
    offset: timedelta, expected: WeatherFreshness
) -> None:
    clock = FixedClock()
    provider = FakeProvider()
    snapshot = fetched_snapshot(clock, provider, FakeStore())
    provider.error = WeatherError(WeatherFailure.NETWORK)
    clock.value += offset

    result = service(FakeLocations(), provider, FakeStore(snapshot), clock).refresh(FARM)

    assert result.freshness is expected
    assert result.failure is WeatherFailure.NETWORK
    assert (result.snapshot is snapshot) is (expected is WeatherFreshness.STALE)


def test_no_cache_and_provider_failure_is_unavailable() -> None:
    provider = FakeProvider()
    provider.error = WeatherError(WeatherFailure.TIMEOUT)

    result = service(FakeLocations(), provider, FakeStore(), FixedClock()).refresh(FARM)

    assert result.freshness is WeatherFreshness.UNAVAILABLE
    assert result.failure is WeatherFailure.TIMEOUT


def test_changed_location_invalidates_even_fresh_cache_and_never_falls_back() -> None:
    clock = FixedClock()
    provider = FakeProvider()
    snapshot = fetched_snapshot(clock, provider, FakeStore())
    provider.calls = 0
    provider.error = WeatherError(WeatherFailure.NETWORK)
    changed = FarmLocation(35, 9)

    result = service(FakeLocations(changed), provider, FakeStore(snapshot), clock).refresh(FARM)

    assert result.freshness is WeatherFreshness.UNAVAILABLE
    assert result.snapshot is None
    assert provider.calls == 1


def test_repeated_success_upserts_same_farm_without_domain_duplicate() -> None:
    clock = FixedClock()
    provider = FakeProvider()
    store = FakeStore()
    instance = service(FakeLocations(), provider, store, clock)

    first = instance.refresh(FARM)
    clock.value += timedelta(minutes=31)
    second = instance.refresh(FARM)

    assert first.snapshot is not None and second.snapshot is not None
    assert first.snapshot.farm_id == second.snapshot.farm_id == FARM
    assert store.upserts == 2


def test_invalid_provider_timeline_is_unavailable() -> None:
    provider = FakeProvider()
    provider.value = replace(provider.value, hourly=provider.value.hourly[:20])

    result = service(FakeLocations(), provider, FakeStore(), FixedClock()).refresh(FARM)

    assert result.failure is WeatherFailure.INVALID_PROVIDER_PAYLOAD


def test_invalid_domain_coordinates_are_rejected() -> None:
    with pytest.raises(ValueError):
        FarmLocation(float("nan"), 10)
    with pytest.raises(ValueError):
        FarmLocation(91, 10)
