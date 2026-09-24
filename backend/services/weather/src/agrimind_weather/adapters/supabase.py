"""Trusted Supabase REST adapters for farm locations and weather snapshots."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import UUID

from agrimind_weather.domain import (
    FarmLocation,
    WeatherAggregates,
    WeatherCurrent,
    WeatherError,
    WeatherFailure,
    WeatherSnapshot,
)


class RestClient(Protocol):
    def request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        prefer: str | None = None,
    ) -> Any: ...


class SupabaseRestClient:
    def __init__(self, url: str, service_role_key: str, *, timeout_seconds: float = 10) -> None:
        if timeout_seconds <= 0:
            raise ValueError("Supabase timeout must be positive")
        self._url = url.rstrip("/")
        self._key = service_role_key
        self._timeout_seconds = timeout_seconds

    def __repr__(self) -> str:
        return f"SupabaseRestClient(url={self._url!r}, service_role_key=*** )"

    def request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        prefer: str | None = None,
    ) -> Any:
        data = None if body is None else json.dumps(body).encode()
        headers = {
            "apikey": self._key,
            "Authorization": f"Bearer {self._key}",
            "Content-Type": "application/json",
        }
        if prefer is not None:
            headers["Prefer"] = prefer
        request = Request(f"{self._url}/rest/v1/{path}", data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                content = response.read()
        except HTTPError as error:
            raise WeatherError(WeatherFailure.STORAGE_ERROR) from error
        except (URLError, TimeoutError, OSError) as error:
            raise WeatherError(WeatherFailure.CACHE_UNAVAILABLE) from error
        if not content:
            return None
        try:
            return json.loads(content)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise WeatherError(WeatherFailure.STORAGE_ERROR) from error


class SupabaseFarmLocationRepository:
    def __init__(self, client: RestClient) -> None:
        self._client = client

    def get_location(self, farm_id: UUID) -> FarmLocation | None:
        rows = self._client.request(
            "GET",
            "farms?"
            + urlencode({"id": f"eq.{farm_id}", "select": "latitude,longitude", "limit": "1"}),
        )
        if not rows:
            return None
        return self._location(rows[0])

    def list_located_farm_ids(self) -> tuple[UUID, ...]:
        rows = self._client.request(
            "GET",
            "farms?"
            + urlencode(
                {
                    "select": "id",
                    "latitude": "not.is.null",
                    "longitude": "not.is.null",
                    "order": "id",
                }
            ),
        )
        if not isinstance(rows, list):
            raise WeatherError(WeatherFailure.STORAGE_ERROR)
        try:
            return tuple(UUID(row["id"]) for row in rows)
        except (KeyError, TypeError, ValueError) as error:
            raise WeatherError(WeatherFailure.STORAGE_ERROR) from error

    @staticmethod
    def _location(row: Any) -> FarmLocation | None:
        if not isinstance(row, dict):
            raise WeatherError(WeatherFailure.STORAGE_ERROR)
        latitude = row.get("latitude")
        longitude = row.get("longitude")
        if latitude is None and longitude is None:
            return None
        if latitude is None or longitude is None:
            raise WeatherError(WeatherFailure.INVALID_LOCATION)
        try:
            return FarmLocation(float(latitude), float(longitude))
        except (TypeError, ValueError) as error:
            raise WeatherError(WeatherFailure.INVALID_LOCATION) from error


class SupabaseWeatherStore:
    def __init__(self, client: RestClient) -> None:
        self._client = client

    def get(self, farm_id: UUID) -> WeatherSnapshot | None:
        rows = self._client.request(
            "GET",
            "weather_snapshots?"
            + urlencode({"farm_id": f"eq.{farm_id}", "select": "*", "limit": "1"}),
        )
        if not rows:
            return None
        try:
            return self._snapshot(rows[0])
        except (KeyError, TypeError, ValueError) as error:
            raise WeatherError(WeatherFailure.STORAGE_ERROR) from error

    def upsert(self, snapshot: WeatherSnapshot) -> None:
        result = self._client.request(
            "POST",
            "weather_snapshots?on_conflict=farm_id",
            body=self._row(snapshot),
            prefer="resolution=merge-duplicates,return=minimal",
        )
        if result is not None:
            raise WeatherError(WeatherFailure.STORAGE_ERROR)

    @staticmethod
    def _row(snapshot: WeatherSnapshot) -> dict[str, Any]:
        current = snapshot.current
        aggregates = snapshot.aggregates
        return {
            "farm_id": str(snapshot.farm_id),
            "provider": snapshot.provider,
            "latitude": snapshot.location.latitude,
            "longitude": snapshot.location.longitude,
            "source_time": current.source_time.isoformat(),
            "fetched_at": snapshot.fetched_at.isoformat(),
            "fresh_until": snapshot.fresh_until.isoformat(),
            "stale_until": snapshot.stale_until.isoformat(),
            "temperature_c": current.temperature_c,
            "relative_humidity_percent": current.relative_humidity_percent,
            "current_precipitation_mm": current.precipitation_mm,
            "current_interval_seconds": current.interval_seconds,
            "weather_code": current.weather_code,
            "wind_speed_kmh": current.wind_speed_kmh,
            "precipitation_last_6h_mm": aggregates.precipitation_last_6h_mm,
            "precipitation_last_12h_mm": aggregates.precipitation_last_12h_mm,
            "precipitation_last_24h_mm": aggregates.precipitation_last_24h_mm,
            "precipitation_previous_24h_mm": (aggregates.precipitation_previous_24h_mm),
            "et0_last_24h_mm": aggregates.et0_last_24h_mm,
        }

    @classmethod
    def _snapshot(cls, row: dict[str, Any]) -> WeatherSnapshot:
        return WeatherSnapshot(
            farm_id=UUID(row["farm_id"]),
            provider=str(row["provider"]),
            location=FarmLocation(float(row["latitude"]), float(row["longitude"])),
            current=WeatherCurrent(
                source_time=cls._time(row["source_time"]),
                temperature_c=float(row["temperature_c"]),
                relative_humidity_percent=float(row["relative_humidity_percent"]),
                precipitation_mm=float(row["current_precipitation_mm"]),
                interval_seconds=int(row["current_interval_seconds"]),
                weather_code=int(row["weather_code"]),
                wind_speed_kmh=float(row["wind_speed_kmh"]),
            ),
            aggregates=WeatherAggregates(
                precipitation_last_6h_mm=float(row["precipitation_last_6h_mm"]),
                precipitation_last_12h_mm=float(row["precipitation_last_12h_mm"]),
                precipitation_last_24h_mm=float(row["precipitation_last_24h_mm"]),
                precipitation_previous_24h_mm=float(row["precipitation_previous_24h_mm"]),
                et0_last_24h_mm=float(row["et0_last_24h_mm"]),
            ),
            fetched_at=cls._time(row["fetched_at"]),
            fresh_until=cls._time(row["fresh_until"]),
            stale_until=cls._time(row["stale_until"]),
        )

    @staticmethod
    def _time(value: Any) -> datetime:
        if not isinstance(value, str):
            raise TypeError("database timestamp must be text")
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("database timestamp must include an offset")
        return parsed.astimezone(UTC)
