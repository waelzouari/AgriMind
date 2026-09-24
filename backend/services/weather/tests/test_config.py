from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

from agrimind_weather.config import WeatherConfig
from agrimind_weather.entrypoints.service import load_environment


def environment() -> dict[str, str]:
    return {
        "AGRIMIND_WEATHER_SUPABASE_URL": "https://project.supabase.co",
        "AGRIMIND_WEATHER_SUPABASE_SERVICE_ROLE_KEY": "server-secret",
    }


def test_defaults_and_secret_redaction() -> None:
    config = WeatherConfig.from_environment(environment())

    assert config.http_timeout_seconds == 5
    assert config.fresh_ttl == timedelta(minutes=30)
    assert config.maximum_stale_age == timedelta(hours=6)
    assert config.refresh_interval == timedelta(minutes=15)
    assert "server-secret" not in repr(config)


@pytest.mark.parametrize(
    "key",
    [
        "AGRIMIND_WEATHER_SUPABASE_URL",
        "AGRIMIND_WEATHER_SUPABASE_SERVICE_ROLE_KEY",
    ],
)
def test_required_configuration_must_be_present(key: str) -> None:
    values = environment()
    del values[key]

    with pytest.raises(ValueError, match="required"):
        WeatherConfig.from_environment(values)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("AGRIMIND_WEATHER_SUPABASE_URL", "http://unsafe"),
        ("AGRIMIND_OPEN_METEO_BASE_URL", "http://unsafe"),
        ("AGRIMIND_WEATHER_HTTP_TIMEOUT_SECONDS", "0"),
        ("AGRIMIND_WEATHER_HTTP_TIMEOUT_SECONDS", "nan"),
        ("AGRIMIND_WEATHER_HTTP_TIMEOUT_SECONDS", "inf"),
        ("AGRIMIND_WEATHER_FRESH_TTL_SECONDS", "0"),
        ("AGRIMIND_WEATHER_FRESH_TTL_SECONDS", "nan"),
        ("AGRIMIND_WEATHER_MAX_STALE_SECONDS", "inf"),
        ("AGRIMIND_WEATHER_REFRESH_INTERVAL_SECONDS", "-1"),
    ],
)
def test_invalid_configuration_fails_before_runtime(key: str, value: str) -> None:
    values = environment()
    values[key] = value
    with pytest.raises(ValueError):
        WeatherConfig.from_environment(values)


def test_maximum_stale_must_exceed_fresh_ttl() -> None:
    values = environment() | {
        "AGRIMIND_WEATHER_FRESH_TTL_SECONDS": "1800",
        "AGRIMIND_WEATHER_MAX_STALE_SECONDS": "1800",
    }
    with pytest.raises(ValueError, match="exceed"):
        WeatherConfig.from_environment(values)


def test_process_environment_overrides_env_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "weather.env"
    path.write_text("KEY=file\n", encoding="utf-8")
    monkeypatch.setenv("KEY", "runtime")
    assert load_environment(path)["KEY"] == "runtime"
