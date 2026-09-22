"""HC-SR04 adapter derived from the working NexusGuard BCM 23/24 driver."""

from __future__ import annotations

import time
from collections.abc import Callable
from contextlib import suppress

from agrimind_edge.adapters.hardware.protocols import GPIO
from agrimind_edge.adapters.hardware.types import TankReading
from agrimind_edge.config import HardwareConfig


def tank_level_from_distance(
    distance_cm: float, *, tank_height_cm: float, tank_offset_cm: float
) -> tuple[float, float]:
    """Return water height and fill percentage using the prototype formula."""

    water_level = max(0.0, tank_height_cm - tank_offset_cm - distance_cm)
    water_pct = min(100.0, max(0.0, (water_level / tank_height_cm) * 100))
    return round(water_level, 1), round(water_pct, 1)


class UltrasonicTankSensor:
    """Measure distance and derive non-critical tank monitoring values."""

    def __init__(
        self,
        gpio: GPIO,
        config: HardwareConfig,
        *,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._gpio = gpio
        self._config = config
        self._sleep = sleep
        self._clock = clock
        self._initialized = False

    @classmethod
    def raspberry_pi(cls, config: HardwareConfig) -> UltrasonicTankSensor:
        import RPi.GPIO as gpio  # type: ignore[import-not-found, import-untyped]

        return cls(gpio, config)

    def initialize(self) -> None:
        if not self._initialized:
            self._gpio.setmode(self._gpio.BCM)
            self._gpio.setwarnings(False)
            self._gpio.setup(self._config.ultrasonic_trigger_gpio, self._gpio.OUT)
            self._gpio.setup(self._config.ultrasonic_echo_gpio, self._gpio.IN)
            self._initialized = True

    def measure_distance(self) -> float:
        """Measure centimetres, returning -1.0 on either one-second timeout."""

        self.initialize()
        trigger = self._config.ultrasonic_trigger_gpio
        echo = self._config.ultrasonic_echo_gpio
        self._gpio.output(trigger, False)
        self._sleep(0.0002)
        self._gpio.output(trigger, True)
        self._sleep(0.00001)
        self._gpio.output(trigger, False)

        pulse_start = self._clock()
        timeout = pulse_start + 1.0
        while self._gpio.input(echo) == 0:
            pulse_start = self._clock()
            if pulse_start > timeout:
                return -1.0

        pulse_end = self._clock()
        timeout = pulse_end + 1.0
        while self._gpio.input(echo) == 1:
            pulse_end = self._clock()
            if pulse_end > timeout:
                return -1.0

        return round((pulse_end - pulse_start) * 17_150, 2)

    def read(self) -> TankReading:
        try:
            distance = self.measure_distance()
            if distance < 0:
                return {
                    "distance_cm": -1,
                    "water_level_cm": 0,
                    "water_pct": 0,
                    "error": "Capteur non détecté",
                }
            water_level, water_pct = tank_level_from_distance(
                distance,
                tank_height_cm=self._config.tank_height_cm,
                tank_offset_cm=self._config.tank_offset_cm,
            )
            return {
                "distance_cm": round(distance, 1),
                "water_level_cm": water_level,
                "water_pct": water_pct,
                "error": None,
            }
        except Exception as error:  # preserve the prototype's error result contract
            return {
                "distance_cm": -1,
                "water_level_cm": 0,
                "water_pct": 0,
                "error": str(error),
            }

    def cleanup(self) -> None:
        if self._initialized:
            with suppress(Exception):
                self._gpio.cleanup(
                    [
                        self._config.ultrasonic_trigger_gpio,
                        self._config.ultrasonic_echo_gpio,
                    ]
                )
            self._initialized = False
