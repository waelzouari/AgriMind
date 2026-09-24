"""Validated, secret-safe weather service configuration."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import timedelta
from urllib.parse import urlparse


def _required(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


def _positive_number(environment: Mapping[str, str], name: str, default: float) -> float:
    raw = environment.get(name, str(default)).strip()
    try:
        value = float(raw)
    except ValueError as error:
        raise ValueError(f"{name} must be a number") from error
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


@dataclass(frozen=True, slots=True)
class SecretValue:
    value: str = field(repr=False)

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("secret value must not be empty")

    def __repr__(self) -> str:
        return "SecretValue('***')"


@dataclass(frozen=True, slots=True)
class WeatherConfig:
    supabase_url: str
    supabase_service_role_key: SecretValue = field(repr=False)
    open_meteo_base_url: str = "https://api.open-meteo.com/v1/forecast"
    http_timeout_seconds: float = 5.0
    fresh_ttl: timedelta = timedelta(minutes=30)
    maximum_stale_age: timedelta = timedelta(hours=6)
    refresh_interval: timedelta = timedelta(minutes=15)

    def __post_init__(self) -> None:
        self._https_url(self.supabase_url, "Supabase URL", origin_only=True)
        self._https_url(self.open_meteo_base_url, "Open-Meteo base URL")
        if self.http_timeout_seconds <= 0:
            raise ValueError("HTTP timeout must be positive")
        if self.fresh_ttl <= timedelta(0):
            raise ValueError("fresh TTL must be positive")
        if self.maximum_stale_age <= self.fresh_ttl:
            raise ValueError("maximum stale age must exceed fresh TTL")
        if self.refresh_interval <= timedelta(0):
            raise ValueError("refresh interval must be positive")

    @staticmethod
    def _https_url(value: str, name: str, *, origin_only: bool = False) -> None:
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.netloc or parsed.query or parsed.fragment:
            raise ValueError(f"{name} must be a safe HTTPS URL")
        if origin_only and parsed.path not in {"", "/"}:
            raise ValueError(f"{name} must be an HTTPS origin without a path")

    def __repr__(self) -> str:
        return (
            "WeatherConfig("
            f"supabase_url={self.supabase_url!r}, supabase_service_role_key=***, "
            f"open_meteo_base_url={self.open_meteo_base_url!r}, "
            f"http_timeout_seconds={self.http_timeout_seconds!r}, "
            f"fresh_ttl={self.fresh_ttl!r}, "
            f"maximum_stale_age={self.maximum_stale_age!r}, "
            f"refresh_interval={self.refresh_interval!r})"
        )

    @classmethod
    def from_environment(cls, environment: Mapping[str, str]) -> WeatherConfig:
        return cls(
            supabase_url=_required(environment, "AGRIMIND_WEATHER_SUPABASE_URL"),
            supabase_service_role_key=SecretValue(
                _required(environment, "AGRIMIND_WEATHER_SUPABASE_SERVICE_ROLE_KEY")
            ),
            open_meteo_base_url=environment.get(
                "AGRIMIND_OPEN_METEO_BASE_URL",
                "https://api.open-meteo.com/v1/forecast",
            ).strip(),
            http_timeout_seconds=_positive_number(
                environment, "AGRIMIND_WEATHER_HTTP_TIMEOUT_SECONDS", 5
            ),
            fresh_ttl=timedelta(
                seconds=_positive_number(environment, "AGRIMIND_WEATHER_FRESH_TTL_SECONDS", 1800)
            ),
            maximum_stale_age=timedelta(
                seconds=_positive_number(environment, "AGRIMIND_WEATHER_MAX_STALE_SECONDS", 21600)
            ),
            refresh_interval=timedelta(
                seconds=_positive_number(
                    environment, "AGRIMIND_WEATHER_REFRESH_INTERVAL_SECONDS", 900
                )
            ),
        )
