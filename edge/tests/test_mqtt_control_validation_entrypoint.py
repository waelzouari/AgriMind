from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from agrimind_edge.adapters.fake import FakeMqttTransport
from agrimind_edge.config import RuntimeConfig
from agrimind_edge.contracts import CommandAcknowledgement, PumpCommand
from agrimind_edge.contracts.enums import AcknowledgementStatus
from agrimind_edge.domain import ReceivedMqttMessage
from agrimind_edge.entrypoints.mqtt_control_validate import (
    build_control_validation_runtime,
    run_pending_fake_schedules,
    sample_on_command,
)

NOW = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)
FARM_ID = UUID("11111111-1111-4111-8111-111111111111")
DEVICE_ID = UUID("22222222-2222-4222-8222-222222222222")


def config() -> RuntimeConfig:
    return RuntimeConfig.from_environment(
        {
            "AGRIMIND_FARM_ID": str(FARM_ID),
            "AGRIMIND_DEVICE_ID": str(DEVICE_ID),
            "AGRIMIND_MQTT_HOST": "mqtt.example.invalid",
            "AGRIMIND_MQTT_PORT": "8883",
            "AGRIMIND_MQTT_TLS_ENABLED": "true",
            "AGRIMIND_MQTT_CA_FILE": "/tmp/example-ca.pem",
            "AGRIMIND_MQTT_USERNAME": "unit-test-control-user",  # pragma: allowlist secret
            "AGRIMIND_MQTT_PASSWORD": "unit-test-control-password",  # pragma: allowlist secret
        }
    )


def test_manual_runtime_uses_fake_pump_and_publishes_accepted_then_completed() -> None:
    transport = FakeMqttTransport()
    runtime = build_control_validation_runtime(config(), transport=transport, clock=lambda: NOW)
    payload = sample_on_command(config(), now=NOW)
    parsed = PumpCommand.from_json(payload, now=NOW)
    runtime.service.start()

    transport.simulate_message(
        ReceivedMqttMessage(runtime.topics.pump_command(), payload.encode(), 1, False)
    )
    run_pending_fake_schedules(runtime.scheduler, {}, monotonic=lambda: 0.0)
    run_pending_fake_schedules(
        runtime.scheduler,
        {id(runtime.scheduler.calls[0]): 0.0},
        monotonic=lambda: 1.0,
    )

    acknowledgements = [
        CommandAcknowledgement.from_json(item.payload)
        for item in transport.publications
        if "/acks/" in item.topic
    ]
    assert [item.status for item in acknowledgements] == [
        AcknowledgementStatus.ACCEPTED,
        AcknowledgementStatus.COMPLETED,
    ]
    assert all(item.command_id == parsed.command_id for item in acknowledgements)
    assert runtime.pump.calls.count("turn_on") == 1
    assert runtime.pump.calls.count("turn_off") == 1


def test_manual_entrypoint_has_no_gpio_dependency() -> None:
    source = Path("edge/src/agrimind_edge/entrypoints/mqtt_control_validate.py").read_text(
        encoding="utf-8"
    )

    assert "GPIO" not in source
    assert "RPi" not in source
    assert "raspberry_pi" not in source
