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
        "AGRIMIND_MQTT_CA_FILE": str(Path.cwd() / "test-ca.pem"),
        "AGRIMIND_MQTT_USERNAME": "device-user",  # pragma: allowlist secret
        "AGRIMIND_MQTT_PASSWORD": "device-password",  # pragma: allowlist secret
        "AGRIMIND_TELEMETRY_INTERVAL_SECONDS": "5",
        "AGRIMIND_CONTRACT_VERSION": "v1",
        "AGRIMIND_SQLITE_PATH": str(Path.cwd() / "edge.sqlite3"),
    }


def test_runtime_configuration_is_validated_and_composes_hardware() -> None:
    config = RuntimeConfig.from_environment(_environment())

    assert config.mqtt.port == 8883
    assert config.mqtt.tls_enabled is True
    assert config.mqtt.ca_file == Path.cwd() / "test-ca.pem"
    assert config.mqtt.contract_version == "v1"
    assert config.mqtt.keepalive_seconds == 60
    assert config.mqtt.reconnect_min_seconds == 1
    assert config.mqtt.reconnect_max_seconds == 60
    assert config.pump_safety.farm_id == config.mqtt.farm_id
    assert config.pump_safety.device_id == config.mqtt.device_id
    assert config.pump_safety.max_duration_seconds == 600
    assert config.hardware.pump_relay_gpio == 18
    assert config.persistence.database_path == Path.cwd() / "edge.sqlite3"
    assert config.scheduler.enabled is False
    assert config.scheduler.poll_interval_seconds == 5
    assert config.scheduler.max_lateness_seconds == 30
    assert config.inference.max_age_seconds == 30


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
        ("AGRIMIND_SQLITE_PATH", "relative/edge.sqlite3", "absolute path"),
        ("AGRIMIND_IRRIGATION_INFERENCE_MAX_AGE_SECONDS", "0", "between 1 and 3600"),
        ("AGRIMIND_IRRIGATION_INFERENCE_MAX_AGE_SECONDS", "3601", "between 1 and 3600"),
        ("AGRIMIND_SCHEDULER_ENABLED", "yes", "must be true or false"),
        ("AGRIMIND_SCHEDULER_POLL_INTERVAL_SECONDS", "0.49", "between 0.5 and 60"),
        ("AGRIMIND_SCHEDULER_POLL_INTERVAL_SECONDS", "61", "between 0.5 and 60"),
        ("AGRIMIND_SCHEDULE_MAX_LATENESS_SECONDS", "-1", "between 0 and 300"),
        ("AGRIMIND_SCHEDULE_MAX_LATENESS_SECONDS", "301", "between 0 and 300"),
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


def test_scheduler_configuration_is_explicit_and_cross_field_safe() -> None:
    environment = _environment()
    environment.update(
        {
            "AGRIMIND_SCHEDULER_ENABLED": "true",
            "AGRIMIND_SCHEDULER_POLL_INTERVAL_SECONDS": "5",
            "AGRIMIND_SCHEDULE_MAX_LATENESS_SECONDS": "30",
        }
    )

    config = RuntimeConfig.from_environment(environment)

    assert config.scheduler.enabled is True
    assert config.scheduler.poll_interval_seconds == 5
    assert config.scheduler.max_lateness_seconds == 30


@pytest.mark.parametrize(
    ("poll", "lateness", "message"),
    [
        ("60", "30", "cannot exceed"),
        ("0.5", "0", "positive maximum lateness"),
    ],
)
def test_enabled_scheduler_rejects_incoherent_polling_window(
    poll: str, lateness: str, message: str
) -> None:
    environment = _environment()
    environment.update(
        {
            "AGRIMIND_SCHEDULER_ENABLED": "true",
            "AGRIMIND_SCHEDULER_POLL_INTERVAL_SECONDS": poll,
            "AGRIMIND_SCHEDULE_MAX_LATENESS_SECONDS": lateness,
        }
    )

    with pytest.raises(ValueError, match=message):
        RuntimeConfig.from_environment(environment)


def test_disabled_scheduler_allows_zero_lateness_without_actuation_claim() -> None:
    environment = _environment()
    environment.update(
        {
            "AGRIMIND_SCHEDULER_ENABLED": "false",
            "AGRIMIND_SCHEDULER_POLL_INTERVAL_SECONDS": "0.5",
            "AGRIMIND_SCHEDULE_MAX_LATENESS_SECONDS": "0",
        }
    )

    config = RuntimeConfig.from_environment(environment)

    assert config.scheduler.enabled is False
    assert config.scheduler.max_lateness_seconds == 0


def test_reconnect_minimum_cannot_exceed_maximum() -> None:
    environment = _environment()
    environment["AGRIMIND_MQTT_RECONNECT_MIN_SECONDS"] = "30"
    environment["AGRIMIND_MQTT_RECONNECT_MAX_SECONDS"] = "10"

    with pytest.raises(ValueError, match="minimum <= maximum"):
        RuntimeConfig.from_environment(environment)


def test_local_fallback_is_explicit_and_uses_separate_redacted_credentials() -> None:
    environment = _environment()
    environment.update(
        {
            "AGRIMIND_MQTT_FAILOVER_ENABLED": "true",
            "AGRIMIND_LOCAL_MQTT_HOST": "127.0.0.1",
            "AGRIMIND_LOCAL_MQTT_PORT": "1883",
            "AGRIMIND_LOCAL_MQTT_USERNAME": "local-device",
            "AGRIMIND_LOCAL_MQTT_PASSWORD": "test-local-pass",  # pragma: allowlist secret
        }
    )
    config = RuntimeConfig.from_environment(environment)

    assert config.failover.enabled is True
    assert config.local_mqtt is not None
    assert config.local_mqtt.tls_enabled is False
    assert config.local_credentials is not None
    assert "test-local-pass" not in repr(config)


def test_enabled_local_tls_requires_ca_file() -> None:
    environment = _environment()
    environment.update(
        {
            "AGRIMIND_MQTT_FAILOVER_ENABLED": "true",
            "AGRIMIND_LOCAL_MQTT_HOST": "127.0.0.1",
            "AGRIMIND_LOCAL_MQTT_USERNAME": "local-device",
            "AGRIMIND_LOCAL_MQTT_PASSWORD": "test-local-pass",  # pragma: allowlist secret
            "AGRIMIND_LOCAL_MQTT_TLS_ENABLED": "true",
        }
    )

    with pytest.raises(ValueError, match="CA file is required"):
        RuntimeConfig.from_environment(environment)
