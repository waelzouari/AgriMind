"""Timestamp-based rolling aggregation of complete hourly provider buckets."""

from __future__ import annotations

from datetime import timedelta
from itertools import pairwise

from agrimind_weather.domain import HourlyWeather, ProviderWeather, WeatherAggregates


def aggregate_weather(provider_weather: ProviderWeather) -> WeatherAggregates:
    hourly = provider_weather.hourly
    if len(hourly) < 48:
        raise ValueError("at least 48 complete hourly buckets are required")
    for previous, current in pairwise(hourly):
        if current.time - previous.time != timedelta(hours=1):
            raise ValueError("hourly timestamps must be strictly contiguous")

    reference = max(
        (bucket.time for bucket in hourly if bucket.time <= provider_weather.current.source_time),
        default=None,
    )
    if reference is None:
        raise ValueError("no complete hourly bucket exists at the reference time")

    def window(hours_start: int, hours_end: int = 0) -> tuple[HourlyWeather, ...]:
        lower = reference - timedelta(hours=hours_start)
        upper = reference - timedelta(hours=hours_end)
        buckets = tuple(bucket for bucket in hourly if lower < bucket.time <= upper)
        expected = hours_start - hours_end
        if len(buckets) != expected:
            raise ValueError("hourly payload does not cover the required aggregation window")
        return buckets

    last_6 = window(6)
    last_12 = window(12)
    last_24 = window(24)
    previous_24 = window(48, 24)
    return WeatherAggregates(
        precipitation_last_6h_mm=sum(bucket.precipitation_mm for bucket in last_6),
        precipitation_last_12h_mm=sum(bucket.precipitation_mm for bucket in last_12),
        precipitation_last_24h_mm=sum(bucket.precipitation_mm for bucket in last_24),
        precipitation_previous_24h_mm=sum(bucket.precipitation_mm for bucket in previous_24),
        et0_last_24h_mm=sum(bucket.et0_mm for bucket in last_24),
    )
