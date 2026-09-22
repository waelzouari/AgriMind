from pathlib import Path

import pytest

from agrimind_edge.config import RuntimeConfig


def _environment() -> dict[str, str]:
    return {
        "AGRIMIND_FARM_ID": "11111111-1111-4111-8111-111111111111",
        "AGRIMIND_DEVICE_ID": "22222222-2222-4222-8222-222222222222",
        "AGRIMIND_MQTT_HOST": "mqtt.example.invalid",
        "AGRIMIND_MQTT_PORT": "8883",
        "AGRIMIND_MQTT_TLS_ENABLED": "true",
        "AGRIMIND_MQTT_CA_FILE": "/etc/agrimind/certs/ca.pem",
        "AGRIMIND_MQTT_USERNAME": "device-user",  # pragma: allowlist secret
        "AGRIMIND_MQTT_PASSWORD": "device-password",  # pragma: allowlist secret
        "AGRIMIND_TELEMETRY_INTERVAL_SECONDS": "5",
        "AGRIMIND_CONTRACT_VERSION": "v1",
    }


def test_runtime_configuration_is_validated_and_composes_hardware() -> None:
    config = RuntimeConfig.from_environment(_environment())

    assert config.mqtt.port == 8883
    assert config.mqtt.tls_enabled is True
    assert config.mqtt.ca_file == Path("/etc/agrimind/certs/ca.pem")
    assert config.mqtt.contract_version == "v1"
    assert config.mqtt.keepalive_seconds == 60
    assert config.mqtt.reconnect_min_seconds == 1
    assert config.mqtt.reconnect_max_seconds == 60
    assert config.pump_safety.farm_id == config.mqtt.farm_id
    assert config.pump_safety.device_id == config.mqtt.device_id
    assert config.pump_safety.max_duration_seconds == 600
    assert config.hardware.pump_relay_gpio == 18


def test_runtime_configuration_repr_redacts_secrets() -> None:
    config = RuntimeConfig.from_environment(_environment())

    rendered = repr(config)
    assert "device-user" not in rendered
    assert "device-password" not in rendered
    assert "username='***'" in rendered
    assert "password='***'" in rendered


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("AGRIMIND_FARM_ID", "00000000-0000-0000-0000-000000000000", "non-zero"),
        ("AGRIMIND_MQTT_HOST", "https://mqtt.example.invalid/path", "hostname"),
        ("AGRIMIND_MQTT_PORT", "70000", "between 1 and 65535"),
        ("AGRIMIND_MQTT_TLS_ENABLED", "yes", "must be true or false"),
        ("AGRIMIND_MQTT_CA_FILE", "relative/ca.pem", "absolute path"),
        ("AGRIMIND_TELEMETRY_INTERVAL_SECONDS", "0", "between 1 and 3600"),
        ("AGRIMIND_CONTRACT_VERSION", "v2", "unsupported contract version"),
        ("AGRIMIND_MQTT_KEEPALIVE_SECONDS", "9", "between 10 and 3600"),
        ("AGRIMIND_MQTT_RECONNECT_MIN_SECONDS", "0", "reconnect delays"),
        ("AGRIMIND_MQTT_RECONNECT_MAX_SECONDS", "3601", "reconnect delays"),
        ("AGRIMIND_PUMP_MAX_DURATION_SECONDS", "0", "between 1 and 600"),
        ("AGRIMIND_PUMP_MAX_DURATION_SECONDS", "601", "between 1 and 600"),
    ],
)
def test_invalid_runtime_configuration_fails_fast(name: str, value: str, message: str) -> None:
    environment = _environment()
    environment[name] = value

    with pytest.raises(ValueError, match=message):
        RuntimeConfig.from_environment(environment)


def test_tls_requires_ca_file() -> None:
    environment = _environment()
    environment["AGRIMIND_MQTT_CA_FILE"] = ""

    with pytest.raises(ValueError, match="CA file is required"):
        RuntimeConfig.from_environment(environment)


def test_reconnect_minimum_cannot_exceed_maximum() -> None:
    environment = _environment()
    environment["AGRIMIND_MQTT_RECONNECT_MIN_SECONDS"] = "30"
    environment["AGRIMIND_MQTT_RECONNECT_MAX_SECONDS"] = "10"

    with pytest.raises(ValueError, match="minimum <= maximum"):
        RuntimeConfig.from_environment(environment)
