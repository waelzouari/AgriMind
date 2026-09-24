"""Run the periodic AGM-019 weather refresh service."""

from __future__ import annotations

import argparse
import logging
import os
import signal
from datetime import UTC, datetime
from pathlib import Path
from threading import Event

from dotenv import dotenv_values

from agrimind_weather.adapters.open_meteo import OpenMeteoWeatherProvider
from agrimind_weather.adapters.supabase import (
    SupabaseFarmLocationRepository,
    SupabaseRestClient,
    SupabaseWeatherStore,
)
from agrimind_weather.application.runner import WeatherRunner
from agrimind_weather.application.weather_service import WeatherService
from agrimind_weather.config import WeatherConfig


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


def load_environment(path: Path) -> dict[str, str]:
    values = dotenv_values(path)
    environment = {key: value for key, value in values.items() if value is not None}
    environment.update(os.environ)
    return environment


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    config = WeatherConfig.from_environment(load_environment(arguments.env_file))
    logging.basicConfig(level=os.environ.get("AGRIMIND_LOG_LEVEL", "INFO"))
    rest = SupabaseRestClient(
        config.supabase_url,
        config.supabase_service_role_key.value,
    )
    locations = SupabaseFarmLocationRepository(rest)
    service = WeatherService(
        locations,
        OpenMeteoWeatherProvider(
            config.open_meteo_base_url,
            timeout_seconds=config.http_timeout_seconds,
        ),
        SupabaseWeatherStore(rest),
        SystemClock(),
        fresh_ttl=config.fresh_ttl,
        maximum_stale_age=config.maximum_stale_age,
    )
    stopped = Event()

    def request_stop(signum: int, frame: object) -> None:
        del signum, frame
        stopped.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    WeatherRunner(
        locations,
        service,
        refresh_interval=config.refresh_interval,
        wait=stopped.wait,
    ).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
