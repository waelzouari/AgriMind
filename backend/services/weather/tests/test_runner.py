from __future__ import annotations

from datetime import timedelta
from typing import Any

from fakes import FARM, OTHER_FARM, FakeLocations

from agrimind_weather.application.runner import WeatherRunner


class RecordingService:
    def __init__(self) -> None:
        self.calls: list[Any] = []
        self.failing_farm: Any = None

    def refresh(self, farm_id: Any) -> None:
        self.calls.append(farm_id)
        if farm_id == self.failing_farm:
            raise RuntimeError("safe synthetic failure")


def test_zero_one_and_multiple_farms_are_processed_without_sleep() -> None:
    locations = FakeLocations()
    recording = RecordingService()
    runner = WeatherRunner(
        locations,
        recording,  # type: ignore[arg-type]
        refresh_interval=timedelta(minutes=15),
        wait=lambda _: True,
    )

    locations.farm_ids = ()
    runner.run_iteration()
    locations.farm_ids = (FARM,)
    runner.run_iteration()
    locations.farm_ids = (FARM, OTHER_FARM)
    runner.run_iteration()

    assert recording.calls == [FARM, FARM, OTHER_FARM]


def test_failure_on_one_farm_does_not_block_the_next() -> None:
    locations = FakeLocations()
    locations.farm_ids = (FARM, OTHER_FARM)
    recording = RecordingService()
    recording.failing_farm = FARM
    runner = WeatherRunner(
        locations,
        recording,  # type: ignore[arg-type]
        refresh_interval=timedelta(minutes=15),
        wait=lambda _: True,
    )

    runner.run_iteration()

    assert recording.calls == [FARM, OTHER_FARM]


def test_periodic_runner_stops_without_real_sleep() -> None:
    waits: list[float] = []
    locations = FakeLocations()
    recording = RecordingService()

    WeatherRunner(
        locations,
        recording,  # type: ignore[arg-type]
        refresh_interval=timedelta(minutes=15),
        wait=lambda seconds: waits.append(seconds) is None,
    ).run()

    assert recording.calls == [FARM]
    assert waits == [900]
