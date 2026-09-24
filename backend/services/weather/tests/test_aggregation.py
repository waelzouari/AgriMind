from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest
from fakes import provider_weather

from agrimind_weather.application.aggregation import aggregate_weather
from agrimind_weather.domain import ProviderWeather


def test_rolling_windows_use_timestamp_boundaries() -> None:
    data = provider_weather(rain=1, et0=0.25)

    result = aggregate_weather(data)

    assert result.precipitation_last_6h_mm == 6
    assert result.precipitation_last_12h_mm == 12
    assert result.precipitation_last_24h_mm == 24
    assert result.precipitation_previous_24h_mm == 24
    assert result.et0_last_24h_mm == 6


def test_future_forecast_bucket_is_not_aggregated() -> None:
    data = provider_weather()
    future = replace(
        data.hourly[-1],
        time=data.hourly[-1].time + timedelta(hours=1),
        precipitation_mm=999,
        et0_mm=999,
    )
    result = aggregate_weather(ProviderWeather(data.current, (*data.hourly, future)))

    assert result.precipitation_last_6h_mm == 6
    assert result.et0_last_24h_mm == 6


def test_exactly_48_complete_buckets_cover_both_24_hour_windows() -> None:
    data = provider_weather(rain=1, et0=0.25)

    result = aggregate_weather(ProviderWeather(data.current, data.hourly[1:]))

    assert result.precipitation_last_24h_mm == 24
    assert result.precipitation_previous_24h_mm == 24
    assert result.et0_last_24h_mm == 6


@pytest.mark.parametrize("kind", ["missing", "out_of_order", "gap"])
def test_invalid_hourly_timeline_is_rejected(kind: str) -> None:
    data = provider_weather()
    hourly = list(data.hourly)
    if kind == "missing":
        hourly.pop(20)
    elif kind == "out_of_order":
        hourly[10], hourly[11] = hourly[11], hourly[10]
    else:
        hourly[10] = replace(hourly[10], time=hourly[10].time + timedelta(minutes=1))

    with pytest.raises(ValueError):
        aggregate_weather(ProviderWeather(data.current, tuple(hourly)))
