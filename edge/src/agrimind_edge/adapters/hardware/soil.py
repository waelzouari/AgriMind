"""ADS1115 soil-moisture adapter preserving NexusGuard calibration behavior."""

from __future__ import annotations

import time
from collections.abc import Callable

from agrimind_edge.adapters.hardware.protocols import AnalogChannel
from agrimind_edge.adapters.hardware.types import SoilReading
from agrimind_edge.config import HardwareConfig


def soil_moisture_percent(raw: int, *, dry_raw: int, wet_raw: int) -> float:
    """Convert a raw ADC value using the prototype's clamped linear formula."""

    if dry_raw == wet_raw:
        raise ValueError("soil dry and wet calibration values must differ")
    humidity = (dry_raw - raw) / (dry_raw - wet_raw) * 100
    return round(max(0.0, min(100.0, humidity)), 1)


class SoilMoistureSensor:
    """Read and average ADS1115 A0 values before converting to percent."""

    def __init__(
        self,
        channel_factory: Callable[[], AnalogChannel],
        config: HardwareConfig,
        *,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._channel_factory = channel_factory
        self._config = config
        self._sleep = sleep
        self._channel: AnalogChannel | None = None

    @classmethod
    def raspberry_pi(cls, config: HardwareConfig) -> SoilMoistureSensor:
        """Create a real ADS1115 adapter without importing Pi libraries in CI."""

        def create_channel() -> AnalogChannel:
            import adafruit_ads1x15.ads1115 as ads  # type: ignore[import-not-found]
            import board  # type: ignore[import-not-found]
            import busio  # type: ignore[import-not-found]
            from adafruit_ads1x15.analog_in import AnalogIn  # type: ignore[import-not-found]

            i2c = busio.I2C(board.SCL, board.SDA)
            converter = ads.ADS1115(i2c)
            return AnalogIn(converter, config.soil_ads1115_channel)  # type: ignore[no-any-return]

        return cls(create_channel, config)

    def _get_channel(self) -> AnalogChannel:
        if self._channel is None:
            self._channel = self._channel_factory()
        return self._channel

    def read_raw_average(self, samples: int = 10) -> int:
        """Average ten samples by default, with the original 50 ms spacing."""

        if samples < 1:
            raise ValueError("samples must be at least 1")
        channel = self._get_channel()
        total = 0
        for _ in range(samples):
            total += channel.value
            self._sleep(0.05)
        return total // samples

    def read(self) -> SoilReading:
        try:
            raw = self.read_raw_average()
            return {
                "soil_humidity": soil_moisture_percent(
                    raw,
                    dry_raw=self._config.soil_dry_raw,
                    wet_raw=self._config.soil_wet_raw,
                ),
                "soil_raw": raw,
                "error": None,
            }
        except Exception as error:  # preserve the prototype's error result contract
            return {"soil_humidity": None, "soil_raw": None, "error": str(error)}
