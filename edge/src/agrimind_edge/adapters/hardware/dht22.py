"""DHT22 adapter derived from the working NexusGuard GPIO 17 driver."""

from __future__ import annotations

import time
from collections.abc import Callable
from contextlib import suppress

from agrimind_edge.adapters.hardware.protocols import DHTDevice
from agrimind_edge.adapters.hardware.types import DHT22Reading
from agrimind_edge.config import HardwareConfig


class DHT22Sensor:
    """Read temperature and air humidity with the prototype retry semantics."""

    def __init__(
        self,
        device_factory: Callable[[], DHTDevice],
        *,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._device_factory = device_factory
        self._sleep = sleep
        self._device: DHTDevice | None = None

    @classmethod
    def raspberry_pi(cls, config: HardwareConfig) -> DHT22Sensor:
        """Create a real adapter; imports Pi-only libraries only when called."""

        def create_device() -> DHTDevice:
            import adafruit_dht  # type: ignore[import-not-found]
            import board  # type: ignore[import-not-found]

            pin = getattr(board, f"D{config.dht22_gpio}")
            return adafruit_dht.DHT22(pin, use_pulseio=False)  # type: ignore[no-any-return]

        return cls(create_device)

    def _get_device(self) -> DHTDevice:
        if self._device is None:
            self._device = self._device_factory()
        return self._device

    def read(self, retries: int = 3) -> DHT22Reading:
        """Return the original dictionary shape and retry RuntimeError three times."""

        if retries < 1:
            raise ValueError("retries must be at least 1")
        device = self._get_device()
        for attempt in range(retries):
            try:
                temperature = device.temperature
                humidity = device.humidity
                if temperature is not None and humidity is not None:
                    return {
                        "temperature": round(float(temperature), 1),
                        "humidity_air": round(float(humidity), 1),
                        "error": None,
                    }
            except RuntimeError as error:
                if attempt < retries - 1:
                    self._sleep(2.0)
                else:
                    self.cleanup()
                    return {"temperature": None, "humidity_air": None, "error": str(error)}
            except Exception as error:  # hardware libraries expose device-specific failures
                self.cleanup()
                return {"temperature": None, "humidity_air": None, "error": str(error)}

        self.cleanup()
        return {
            "temperature": None,
            "humidity_air": None,
            "error": "Max retries reached",
        }

    def cleanup(self) -> None:
        """Release the Adafruit device and allow clean reinitialization."""

        if self._device is not None:
            with suppress(Exception):
                self._device.exit()
            self._device = None
