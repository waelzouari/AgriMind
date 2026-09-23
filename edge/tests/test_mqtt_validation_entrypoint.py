from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID

import pytest

from agrimind_edge.adapters.fake import FakeMqttTransport
from agrimind_edge.config import RuntimeConfig
from agrimind_edge.contracts.models import DeviceStatus, Telemetry
from agrimind_edge.contracts.topics import TopicBuilder
from agrimind_edge.entrypoints.mqtt_validate import (
    load_runtime_config,
    run_validation,
)

FARM_ID = UUID("11111111-1111-4111-8111-111111111111")
DEVICE_ID = UUID("22222222-2222-4222-8222-222222222222")


def environment() -> dict[str, str]:
    return {
        "AGRIMIND_FARM_ID": str(FARM_ID),
        "AGRIMIND_DEVICE_ID": str(DEVICE_ID),
        "AGRIMIND_MQTT_HOST": "mqtt.example.invalid",
        "AGRIMIND_MQTT_PORT": "8883",
        "AGRIMIND_MQTT_TLS_ENABLED": "true",
        "AGRIMIND_MQTT_CA_FILE": "/tmp/example-ca.pem",
        "AGRIMIND_MQTT_USERNAME": "unit-test-mqtt-user",  # pragma: allowlist secret
        "AGRIMIND_MQTT_PASSWORD": "unit-test-mqtt-password",  # pragma: allowlist secret
        "AGRIMIND_CONTRACT_VERSION": "v1",
    }


def write_env(path: Path, values: dict[str, str]) -> None:
    path.write_text(
        "\n".join(f"{key}={value}" for key, value in values.items()) + "\n",
        encoding="utf-8",
    )


def test_loads_explicit_dotenv_without_mutating_process_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env_file = tmp_path / ".env"
    write_env(env_file, environment())
    monkeypatch.delenv("AGRIMIND_MQTT_USERNAME", raising=False)

    config = load_runtime_config(env_file)

    assert config.mqtt.farm_id == FARM_ID
    assert config.mqtt.device_id == DEVICE_ID
    assert config.mqtt.port == 8883
    assert config.mqtt.tls_enabled is True
    assert config.mqtt.ca_file == Path("/tmp/example-ca.pem")
    assert repr(config.credentials) == "MqttCredentials(username='***', password='***')"
    assert "AGRIMIND_MQTT_USERNAME" not in os.environ


def test_missing_env_file_fails_before_transport_construction(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="environment file not found"):
        load_runtime_config(tmp_path / "missing.env")


def test_runs_existing_lifecycle_with_fake_sensors_and_transport() -> None:
    config = RuntimeConfig.from_environment(environment())
    transport = FakeMqttTransport()

    report = run_validation(config, transport=transport)

    topics = TopicBuilder(FARM_ID, DEVICE_ID)
    assert report.wildcard_topic == f"{topics.base}/#"
    assert report.status_topic == topics.device_status()
    assert report.mapped == 4
    assert report.published == 4
    assert transport.last_will is not None
    assert transport.operations.index("configure_last_will") < transport.operations.index("connect")
    assert transport.operations[-1] == "disconnect"

    status_messages = [
        DeviceStatus.from_json(publication.payload)
        for publication in transport.publications
        if publication.topic == topics.device_status()
    ]
    telemetry_messages = [
        Telemetry.from_json(publication.payload)
        for publication in transport.publications
        if "/telemetry/" in publication.topic
    ]
    assert [status.online for status in status_messages] == [True, False]
    assert len(telemetry_messages) == 4
    assert all(publication.qos == 1 for publication in transport.publications)
    assert all(
        publication.retain is False
        for publication in transport.publications
        if "/telemetry/" in publication.topic
    )


def test_timeout_still_disconnects_cleanly_without_publishing() -> None:
    config = RuntimeConfig.from_environment(environment())
    transport = FakeMqttTransport(auto_connect=False)

    with pytest.raises(TimeoutError, match="not confirmed"):
        run_validation(
            config,
            transport=transport,
            wait_for_connection=lambda service, timeout: False,
        )

    assert transport.publications == []
    assert transport.operations[-1] == "disconnect"


def test_entrypoint_source_has_no_pump_or_gpio_dependency() -> None:
    source = Path("edge/src/agrimind_edge/entrypoints/mqtt_validate.py").read_text(encoding="utf-8")

    assert "Pump" not in source
    assert "GPIO" not in source
    assert "RPi" not in source
    assert "raspberry_pi" not in source
