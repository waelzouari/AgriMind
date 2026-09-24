"""One-pass and periodic weather refresh runner."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import timedelta

from agrimind_weather.application.ports import FarmLocationRepository
from agrimind_weather.application.weather_service import WeatherService
from agrimind_weather.domain import WeatherError

LOGGER = logging.getLogger(__name__)


class WeatherRunner:
    def __init__(
        self,
        locations: FarmLocationRepository,
        service: WeatherService,
        *,
        refresh_interval: timedelta,
        wait: Callable[[float], bool],
    ) -> None:
        if refresh_interval <= timedelta(0):
            raise ValueError("refresh interval must be positive")
        self._locations = locations
        self._service = service
        self._refresh_interval = refresh_interval
        self._wait = wait

    def run_iteration(self) -> None:
        try:
            farm_ids = self._locations.list_located_farm_ids()
        except WeatherError as error:
            LOGGER.error(
                "weather.farms.failure",
                extra={"event": "weather.farms.failure", "reason_code": error.failure.value},
            )
            return
        for farm_id in farm_ids:
            try:
                self._service.refresh(farm_id)
            except Exception:
                LOGGER.error(
                    "weather.refresh.unexpected",
                    extra={"event": "weather.refresh.unexpected", "farm_id": str(farm_id)},
                )

    def run(self) -> None:
        while True:
            self.run_iteration()
            if self._wait(self._refresh_interval.total_seconds()):
                return
