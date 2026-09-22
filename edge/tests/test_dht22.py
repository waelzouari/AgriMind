from __future__ import annotations

from collections.abc import Iterable

from agrimind_edge.adapters.hardware.dht22 import DHT22Sensor


class ScriptedDHT:
    def __init__(
        self,
        temperatures: Iterable[float | Exception | None],
        humidities: Iterable[float | Exception | None],
    ) -> None:
        self._temperatures = iter(temperatures)
        self._humidities = iter(humidities)
        self.exited = False

    @property
    def temperature(self) -> float | None:
        value = next(self._temperatures)
        if isinstance(value, Exception):
            raise value
        return value

    @property
    def humidity(self) -> float | None:
        value = next(self._humidities)
        if isinstance(value, Exception):
            raise value
        return value

    def exit(self) -> None:
        self.exited = True


def test_dht22_returns_rounded_temperature_and_humidity() -> None:
    device = ScriptedDHT([24.26], [61.84])
    sensor = DHT22Sensor(lambda: device, sleep=lambda _: None)

    assert sensor.read() == {"temperature": 24.3, "humidity_air": 61.8, "error": None}


def test_dht22_retries_runtime_errors_with_two_second_spacing() -> None:
    device = ScriptedDHT([RuntimeError("transient"), RuntimeError("again"), 25.0], [55.0])
    sleeps: list[float] = []
    sensor = DHT22Sensor(lambda: device, sleep=sleeps.append)

    assert sensor.read() == {"temperature": 25.0, "humidity_air": 55.0, "error": None}
    assert sleeps == [2.0, 2.0]
    assert device.exited is False


def test_dht22_terminal_error_cleans_up_and_can_reinitialize() -> None:
    first = ScriptedDHT([RuntimeError("failed")], [])
    second = ScriptedDHT([22.0], [50.0])
    devices = iter([first, second])
    sensor = DHT22Sensor(lambda: next(devices), sleep=lambda _: None)

    assert sensor.read(retries=1)["error"] == "failed"
    assert first.exited is True
    assert sensor.read() == {"temperature": 22.0, "humidity_air": 50.0, "error": None}


def test_dht22_rejects_invalid_retry_count() -> None:
    sensor = DHT22Sensor(lambda: ScriptedDHT([], []))

    try:
        sensor.read(retries=0)
    except ValueError as error:
        assert str(error) == "retries must be at least 1"
    else:
        raise AssertionError("invalid retries were accepted")
