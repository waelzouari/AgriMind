import pytest

from agrimind_edge.config import HardwareConfig


def test_verified_hardware_defaults() -> None:
    config = HardwareConfig()

    assert config.dht22_gpio == 17
    assert config.pump_relay_gpio == 18
    assert config.relay_active_low is True
    assert config.ultrasonic_trigger_gpio == 23
    assert config.ultrasonic_echo_gpio == 24
    assert config.soil_ads1115_channel == 0
    assert config.soil_dry_raw == 28_000
    assert config.soil_wet_raw == 11_000


@pytest.mark.parametrize(
    ("environment", "message"),
    [
        ({"AGRIMIND_GPIO_RELAY": "not-a-pin"}, "must be an integer"),
        ({"AGRIMIND_GPIO_DHT22": "28"}, "must be a BCM GPIO"),
        ({"AGRIMIND_RELAY_ACTIVE_LOW": "false"}, "must remain active-low"),
        ({"AGRIMIND_ADS1115_CHANNEL": "4"}, "must be between 0 and 3"),
        (
            {"AGRIMIND_SOIL_DRY_RAW": "12000", "AGRIMIND_SOIL_WET_RAW": "12000"},
            "must differ",
        ),
    ],
)
def test_invalid_environment_configuration_is_rejected(
    environment: dict[str, str], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        HardwareConfig.from_environment(environment)
