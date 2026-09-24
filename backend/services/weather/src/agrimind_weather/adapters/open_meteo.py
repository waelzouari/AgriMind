"""Strict Open-Meteo Forecast API adapter with injectable HTTP transport."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from agrimind_weather.domain import (
    FarmLocation,
    HourlyWeather,
    ProviderWeather,
    WeatherCurrent,
    WeatherError,
    WeatherFailure,
)

CURRENT_FIELDS = (
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "weather_code",
    "wind_speed_10m",
)
HOURLY_FIELDS = ("precipitation", "et0_fao_evapotranspiration")


class HttpTransport(Protocol):
    def get_json(self, url: str, *, timeout_seconds: float) -> Any: ...


class UrllibHttpTransport:
    def get_json(self, url: str, *, timeout_seconds: float) -> Any:
        try:
            with urlopen(Request(url, method="GET"), timeout=timeout_seconds) as response:
                payload = response.read()
        except HTTPError as error:
            raise WeatherError(WeatherFailure.PROVIDER_HTTP_ERROR) from error
        except TimeoutError as error:
            raise WeatherError(WeatherFailure.TIMEOUT) from error
        except (URLError, OSError) as error:
            reason = getattr(error, "reason", None)
            failure = (
                WeatherFailure.TIMEOUT
                if isinstance(reason, TimeoutError)
                else WeatherFailure.NETWORK
            )
            raise WeatherError(failure) from error
        try:
            return json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise WeatherError(WeatherFailure.INVALID_PROVIDER_PAYLOAD) from error


class OpenMeteoWeatherProvider:
    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float,
        transport: HttpTransport | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("Open-Meteo timeout must be positive")
        self._base_url = base_url
        self._timeout_seconds = timeout_seconds
        self._transport = transport or UrllibHttpTransport()

    def fetch(self, location: FarmLocation) -> ProviderWeather:
        query = urlencode(
            {
                "latitude": location.latitude,
                "longitude": location.longitude,
                "current": ",".join(CURRENT_FIELDS),
                "hourly": ",".join(HOURLY_FIELDS),
                "past_hours": 48,
                "forecast_hours": 1,
                "timezone": "UTC",
                "temperature_unit": "celsius",
                "wind_speed_unit": "kmh",
                "precipitation_unit": "mm",
            }
        )
        payload = self._transport.get_json(
            f"{self._base_url}?{query}", timeout_seconds=self._timeout_seconds
        )
        try:
            return self._parse(payload)
        except (KeyError, TypeError, ValueError, OverflowError) as error:
            raise WeatherError(WeatherFailure.INVALID_PROVIDER_PAYLOAD) from error

    @classmethod
    def _parse(cls, payload: Any) -> ProviderWeather:
        if not isinstance(payload, dict):
            raise TypeError("provider payload must be an object")
        current = payload["current"]
        hourly = payload["hourly"]
        if not isinstance(current, dict) or not isinstance(hourly, dict):
            raise TypeError("provider sections must be objects")

        times = cls._list(hourly, "time")
        precipitation = cls._list(hourly, "precipitation")
        et0 = cls._list(hourly, "et0_fao_evapotranspiration")
        if not len(times) == len(precipitation) == len(et0):
            raise ValueError("hourly arrays must have equal lengths")
        buckets = tuple(
            HourlyWeather(
                cls._timestamp(time),
                cls._number(rain),
                cls._number(evapotranspiration),
            )
            for time, rain, evapotranspiration in zip(times, precipitation, et0, strict=True)
        )
        return ProviderWeather(
            current=WeatherCurrent(
                source_time=cls._timestamp(current["time"]),
                temperature_c=cls._number(current["temperature_2m"]),
                relative_humidity_percent=cls._number(current["relative_humidity_2m"]),
                precipitation_mm=cls._number(current["precipitation"]),
                interval_seconds=cls._integer(current["interval"]),
                weather_code=cls._integer(current["weather_code"]),
                wind_speed_kmh=cls._number(current["wind_speed_10m"]),
            ),
            hourly=buckets,
        )

    @staticmethod
    def _list(section: dict[str, Any], name: str) -> list[Any]:
        value = section[name]
        if not isinstance(value, list):
            raise TypeError(f"{name} must be an array")
        return value

    @staticmethod
    def _timestamp(value: Any) -> datetime:
        if not isinstance(value, str):
            raise TypeError("timestamp must be a string")
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)

    @staticmethod
    def _number(value: Any) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("weather value must be numeric")
        return float(value)

    @staticmethod
    def _integer(value: Any) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("weather value must be an integer")
        return int(value)
