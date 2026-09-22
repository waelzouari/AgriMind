"""Physical hardware configuration with verified NexusGuard defaults."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


def _read_int(environment: Mapping[str, str], name: str, default: int) -> int:
    value = environment.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer") from error


def _read_float(environment: Mapping[str, str], name: str, default: float) -> float:
    value = environment.get(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError as error:
        raise ValueError(f"{name} must be a number") from error


@dataclass(frozen=True, slots=True)
class HardwareConfig:
    """Wiring and calibration values verified on the working prototype."""

    dht22_gpio: int = 17
    pump_relay_gpio: int = 18
    relay_active_low: bool = True
    ultrasonic_trigger_gpio: int = 23
    ultrasonic_echo_gpio: int = 24
    soil_ads1115_channel: int = 0
    soil_dry_raw: int = 28_000
    soil_wet_raw: int = 11_000
    tank_height_cm: float = 30.0
    tank_offset_cm: float = 2.0

    def __post_init__(self) -> None:
        gpio_values = {
            "dht22_gpio": self.dht22_gpio,
            "pump_relay_gpio": self.pump_relay_gpio,
            "ultrasonic_trigger_gpio": self.ultrasonic_trigger_gpio,
            "ultrasonic_echo_gpio": self.ultrasonic_echo_gpio,
        }
        for name, value in gpio_values.items():
            if not 0 <= value <= 27:
                raise ValueError(f"{name} must be a BCM GPIO number from 0 to 27")
        if len(set(gpio_values.values())) != len(gpio_values):
            raise ValueError("GPIO assignments must be unique")
        if self.soil_ads1115_channel not in range(4):
            raise ValueError("soil_ads1115_channel must be between 0 and 3")
        if self.soil_dry_raw == self.soil_wet_raw:
            raise ValueError("soil dry and wet calibration values must differ")
        if self.tank_height_cm <= 0:
            raise ValueError("tank_height_cm must be positive")
        if not 0 <= self.tank_offset_cm < self.tank_height_cm:
            raise ValueError("tank_offset_cm must be non-negative and less than tank height")
        if not self.relay_active_low:
            raise ValueError("the verified pump relay must remain active-low")

    @classmethod
    def from_environment(cls, environment: Mapping[str, str]) -> HardwareConfig:
        """Build configuration from validated, non-secret environment values."""

        active_low = environment.get("AGRIMIND_RELAY_ACTIVE_LOW", "true").strip().lower()
        if active_low not in {"true", "false"}:
            raise ValueError("AGRIMIND_RELAY_ACTIVE_LOW must be true or false")
        return cls(
            dht22_gpio=_read_int(environment, "AGRIMIND_GPIO_DHT22", 17),
            pump_relay_gpio=_read_int(environment, "AGRIMIND_GPIO_RELAY", 18),
            relay_active_low=active_low == "true",
            ultrasonic_trigger_gpio=_read_int(
                environment, "AGRIMIND_GPIO_ULTRASONIC_TRIGGER", 23
            ),
            ultrasonic_echo_gpio=_read_int(
                environment, "AGRIMIND_GPIO_ULTRASONIC_ECHO", 24
            ),
            soil_ads1115_channel=_read_int(environment, "AGRIMIND_ADS1115_CHANNEL", 0),
            soil_dry_raw=_read_int(environment, "AGRIMIND_SOIL_DRY_RAW", 28_000),
            soil_wet_raw=_read_int(environment, "AGRIMIND_SOIL_WET_RAW", 11_000),
            tank_height_cm=_read_float(environment, "AGRIMIND_TANK_HEIGHT_CM", 30.0),
            tank_offset_cm=_read_float(environment, "AGRIMIND_TANK_OFFSET_CM", 2.0),
        )
