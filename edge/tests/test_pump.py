from agrimind_edge.adapters.hardware.pump import PumpRelay
from agrimind_edge.config import HardwareConfig
from tests.fakes import FailingCleanupGPIO, FakeGPIO


def test_pump_initialization_forces_active_low_relay_off() -> None:
    gpio = FakeGPIO()
    pump = PumpRelay(gpio, HardwareConfig())

    pump.initialize()

    assert gpio.mode == gpio.BCM
    assert gpio.setups == [(18, gpio.OUT, gpio.HIGH)]
    assert gpio.outputs == [(18, gpio.HIGH)]
    assert pump.get_state() is False


def test_pump_on_is_low_and_off_is_high() -> None:
    gpio = FakeGPIO()
    pump = PumpRelay(gpio, HardwareConfig())

    assert pump.turn_on() == {"pump": True, "message": "Pompe activée"}
    assert pump.get_state() is True
    assert gpio.outputs[-1] == (18, gpio.LOW)

    assert pump.turn_off() == {"pump": False, "message": "Pompe éteinte"}
    assert pump.get_state() is False
    assert gpio.outputs[-1] == (18, gpio.HIGH)


def test_pump_cleanup_forces_off_before_releasing_gpio() -> None:
    gpio = FakeGPIO()
    pump = PumpRelay(gpio, HardwareConfig())
    pump.turn_on()

    pump.cleanup()

    assert gpio.outputs[-1] == (18, gpio.HIGH)
    assert gpio.cleaned == [[18]]
    assert pump.get_state() is False


def test_pump_state_is_safe_even_if_gpio_cleanup_fails() -> None:
    gpio = FailingCleanupGPIO()
    pump = PumpRelay(gpio, HardwareConfig())
    pump.turn_on()

    pump.cleanup()

    assert pump.get_state() is False
