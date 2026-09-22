"""Active-low pump relay adapter derived from the NexusGuard GPIO 18 driver."""

from __future__ import annotations

from agrimind_edge.adapters.hardware.protocols import GPIO
from agrimind_edge.adapters.hardware.types import PumpResult
from agrimind_edge.config import HardwareConfig


class PumpRelay:
    """Control the verified active-low relay and default it to physical OFF."""

    def __init__(self, gpio: GPIO, config: HardwareConfig) -> None:
        self._gpio = gpio
        self._config = config
        self._initialized = False
        self._pump_active = False

    @classmethod
    def raspberry_pi(cls, config: HardwareConfig) -> PumpRelay:
        import RPi.GPIO as gpio  # type: ignore[import-not-found, import-untyped]

        return cls(gpio, config)

    def initialize(self) -> None:
        """Configure BCM output and immediately drive HIGH (relay/pump OFF)."""

        if not self._initialized:
            self._gpio.setmode(self._gpio.BCM)
            self._gpio.setwarnings(False)
            # RPi.GPIO's initial value prevents an active-low startup pulse
            # between configuring the pin as output and the explicit OFF write.
            self._gpio.setup(
                self._config.pump_relay_gpio,
                self._gpio.OUT,
                initial=self._gpio.HIGH,
            )
            self._gpio.output(self._config.pump_relay_gpio, self._gpio.HIGH)
            self._initialized = True
            self._pump_active = False

    def get_state(self) -> bool:
        return self._pump_active

    def turn_on(self) -> PumpResult:
        self.initialize()
        self._gpio.output(self._config.pump_relay_gpio, self._gpio.LOW)
        self._pump_active = True
        return {"pump": True, "message": "Pompe activée"}

    def turn_off(self) -> PumpResult:
        self.initialize()
        self._gpio.output(self._config.pump_relay_gpio, self._gpio.HIGH)
        self._pump_active = False
        return {"pump": False, "message": "Pompe éteinte"}

    def toggle(self) -> PumpResult:
        return self.turn_off() if self._pump_active else self.turn_on()

    def cleanup(self) -> None:
        """Best-effort HIGH/OFF before releasing GPIO, even after an error."""

        if self._initialized:
            try:
                self._gpio.output(self._config.pump_relay_gpio, self._gpio.HIGH)
                self._gpio.cleanup([self._config.pump_relay_gpio])
            except Exception:
                pass
            finally:
                self._initialized = False
                self._pump_active = False
