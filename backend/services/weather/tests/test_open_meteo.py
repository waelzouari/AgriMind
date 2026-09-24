from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from io import BytesIO
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse

import pytest
from fakes import LOCATION

from agrimind_weather.adapters.open_meteo import (
    OpenMeteoWeatherProvider,
    UrllibHttpTransport,
)
from agrimind_weather.domain import WeatherError, WeatherFailure


def payload() -> dict[str, Any]:
    start = datetime(2026, 9, 21, 12, tzinfo=UTC)
    return {
        "current": {
            "time": "2026-09-23T12:00",
            "interval": 900,
            "temperature_2m": 25,
            "relative_humidity_2m": 60,
            "precipitation": 0.1,
            "weather_code": 2,
            "wind_speed_10m": 12,
        },
        "hourly": {
            "time": [
                (start + timedelta(hours=index)).strftime("%Y-%m-%dT%H:%M") for index in range(49)
            ],
            "precipitation": [1] * 49,
            "et0_fao_evapotranspiration": [0.25] * 49,
        },
    }


class FakeTransport:
    def __init__(self, value: Any) -> None:
        self.value = value
        self.url = ""
        self.timeout = 0.0
        self.error: WeatherError | None = None

    def get_json(self, url: str, *, timeout_seconds: float) -> Any:
        self.url = url
        self.timeout = timeout_seconds
        if self.error:
            raise self.error
        return self.value


def test_request_contract_and_valid_payload() -> None:
    transport = FakeTransport(payload())
    provider = OpenMeteoWeatherProvider(
        "https://api.open-meteo.com/v1/forecast",
        timeout_seconds=5,
        transport=transport,
    )

    result = provider.fetch(LOCATION)
    query = parse_qs(urlparse(transport.url).query)

    assert query == {
        "latitude": [str(LOCATION.latitude)],
        "longitude": [str(LOCATION.longitude)],
        "current": [
            "temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m"
        ],
        "hourly": ["precipitation,et0_fao_evapotranspiration"],
        "past_hours": ["48"],
        "forecast_hours": ["1"],
        "timezone": ["UTC"],
        "temperature_unit": ["celsius"],
        "wind_speed_unit": ["kmh"],
        "precipitation_unit": ["mm"],
    }
    assert transport.timeout == 5
    assert result.current.source_time == datetime(2026, 9, 23, 12, tzinfo=UTC)
    assert result.current.interval_seconds == 900
    assert len(result.hourly) == 49


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value.pop("current"),
        lambda value: value["current"].__setitem__("temperature_2m", None),
        lambda value: value["current"].__setitem__("precipitation", True),
        lambda value: value["current"].__setitem__("interval", True),
        lambda value: value["current"].__setitem__("time", "invalid"),
        lambda value: value["hourly"].__setitem__("precipitation", [1]),
        lambda value: value["hourly"].__setitem__("et0_fao_evapotranspiration", [None] * 49),
    ],
)
def test_malformed_or_incomplete_payload_is_safely_rejected(mutate: Any) -> None:
    value = payload()
    mutate(value)
    provider = OpenMeteoWeatherProvider(
        "https://api.open-meteo.com/v1/forecast",
        timeout_seconds=5,
        transport=FakeTransport(value),
    )

    with pytest.raises(WeatherError) as captured:
        provider.fetch(LOCATION)
    assert captured.value.failure is WeatherFailure.INVALID_PROVIDER_PAYLOAD


@pytest.mark.parametrize(
    "failure",
    [WeatherFailure.TIMEOUT, WeatherFailure.NETWORK, WeatherFailure.PROVIDER_HTTP_ERROR],
)
def test_transport_failures_are_preserved(failure: WeatherFailure) -> None:
    transport = FakeTransport(json.loads("{}"))
    transport.error = WeatherError(failure)
    provider = OpenMeteoWeatherProvider(
        "https://example.test", timeout_seconds=5, transport=transport
    )

    with pytest.raises(WeatherError) as captured:
        provider.fetch(LOCATION)
    assert captured.value.failure is failure


class FakeResponse:
    def __init__(self, content: bytes) -> None:
        self.content = content

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        pass

    def read(self) -> bytes:
        return self.content


@pytest.mark.parametrize("status", [400, 429, 500])
def test_urllib_transport_maps_http_errors_without_exposing_body(
    status: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise HTTPError(
            "https://example.test",
            status,
            "sensitive provider body",
            {},
            BytesIO(b'{"reason":"sensitive"}'),
        )

    monkeypatch.setattr("agrimind_weather.adapters.open_meteo.urlopen", fail)
    with pytest.raises(WeatherError) as captured:
        UrllibHttpTransport().get_json("https://example.test", timeout_seconds=5)
    assert captured.value.failure is WeatherFailure.PROVIDER_HTTP_ERROR
    assert "sensitive" not in str(captured.value)


@pytest.mark.parametrize(
    ("error", "failure"),
    [
        (TimeoutError(), WeatherFailure.TIMEOUT),
        (URLError("offline"), WeatherFailure.NETWORK),
        (URLError(TimeoutError()), WeatherFailure.TIMEOUT),
    ],
)
def test_urllib_transport_maps_network_failures(
    error: Exception,
    failure: WeatherFailure,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise error

    monkeypatch.setattr("agrimind_weather.adapters.open_meteo.urlopen", fail)
    with pytest.raises(WeatherError) as captured:
        UrllibHttpTransport().get_json("https://example.test", timeout_seconds=5)
    assert captured.value.failure is failure


def test_urllib_transport_rejects_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "agrimind_weather.adapters.open_meteo.urlopen",
        lambda *args, **kwargs: FakeResponse(b"not-json"),
    )
    with pytest.raises(WeatherError) as captured:
        UrllibHttpTransport().get_json("https://example.test", timeout_seconds=5)
    assert captured.value.failure is WeatherFailure.INVALID_PROVIDER_PAYLOAD
