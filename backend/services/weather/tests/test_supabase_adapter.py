from __future__ import annotations

from datetime import timedelta
from typing import Any

from fakes import FARM, LOCATION, FakeProvider, FakeStore, FixedClock

from agrimind_weather.adapters.supabase import (
    SupabaseFarmLocationRepository,
    SupabaseRestClient,
    SupabaseWeatherStore,
)
from agrimind_weather.application.weather_service import WeatherService


class FakeRestClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, Any] | None, str | None]] = []
        self.response: Any = []

    def request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        prefer: str | None = None,
    ) -> Any:
        self.calls.append((method, path, body, prefer))
        return self.response


def snapshot() -> Any:
    store = FakeStore()
    result = WeatherService(
        FakeLocationRepository(),
        FakeProvider(),
        store,
        FixedClock(),
        fresh_ttl=timedelta(minutes=30),
        maximum_stale_age=timedelta(hours=6),
    ).refresh(FARM)
    return result.snapshot


class FakeLocationRepository:
    def get_location(self, farm_id: Any) -> Any:
        del farm_id
        return LOCATION

    def list_located_farm_ids(self) -> tuple[Any, ...]:
        return (FARM,)


def test_location_repository_maps_missing_pair_and_located_farms() -> None:
    client = FakeRestClient()
    repository = SupabaseFarmLocationRepository(client)

    client.response = [{"latitude": None, "longitude": None}]
    assert repository.get_location(FARM) is None
    client.response = [{"latitude": 36.8065, "longitude": 10.1815}]
    assert repository.get_location(FARM) == LOCATION
    client.response = [{"id": str(FARM)}]
    assert repository.list_located_farm_ids() == (FARM,)
    listing_path = client.calls[-1][1]
    assert "select=id" in listing_path
    assert "latitude=not.is.null" in listing_path
    assert "longitude=not.is.null" in listing_path


def test_weather_store_upserts_by_farm_and_round_trips_row() -> None:
    client = FakeRestClient()
    store = SupabaseWeatherStore(client)
    value = snapshot()
    assert value is not None

    client.response = None
    store.upsert(value)
    method, path, body, prefer = client.calls[-1]
    assert method == "POST"
    assert path == "weather_snapshots?on_conflict=farm_id"
    assert body is not None and body["farm_id"] == str(FARM)
    assert prefer == "resolution=merge-duplicates,return=minimal"

    client.response = [body]
    assert store.get(FARM) == value


def test_supabase_client_repr_never_exposes_service_role() -> None:
    secret = "weather-service-role-secret"  # pragma: allowlist secret
    client = SupabaseRestClient("https://example.supabase.co", secret)
    assert secret not in repr(client)
