from __future__ import annotations

import json
import logging
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from itertools import count
from pathlib import Path
from uuid import UUID

import pytest

from agrimind_edge.adapters.fake import (
    FakeDeviceStatusSource,
    FakeMqttTransport,
    FakePump,
    FakeScheduler,
)
from agrimind_edge.application import (
    CloudMqttService,
    MqttAcknowledgementPublisher,
    MqttPumpCommandProcessor,
    PumpCommandHandler,
    SafePumpController,
    TelemetryMapper,
)
from agrimind_edge.config import PumpSafetyConfig
from agrimind_edge.contracts import CommandAcknowledgement, PumpCommand
from agrimind_edge.contracts.enums import AcknowledgementStatus, DeviceHealth, PumpAction
from agrimind_edge.contracts.topics import TopicBuilder
from agrimind_edge.domain import DeviceRuntimeStatus, ReceivedMqttMessage

NOW = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)
FARM_ID = UUID("11111111-1111-4111-8111-111111111111")
DEVICE_ID = UUID("22222222-2222-4222-8222-222222222222")
USER_ID = UUID("55555555-5555-4555-8555-555555555555")
COMMAND_ID = UUID(int=10)


def command(
    *,
    command_id: UUID = COMMAND_ID,
    farm_id: UUID = FARM_ID,
    device_id: UUID = DEVICE_ID,
    action: PumpAction = PumpAction.ON,
    duration_seconds: int | None = 10,
    issued_at: datetime = NOW - timedelta(seconds=1),
    expires_at: datetime = NOW + timedelta(seconds=30),
) -> PumpCommand:
    return PumpCommand(
        command_id=command_id,
        farm_id=farm_id,
        device_id=device_id,
        action=action,
        duration_seconds=duration_seconds if action is PumpAction.ON else None,
        issued_at=issued_at,
        expires_at=expires_at,
        requested_by=USER_ID,
    )


@dataclass
class Harness:
    transport: FakeMqttTransport
    pump: FakePump
    scheduler: FakeScheduler
    topics: TopicBuilder
    processor: MqttPumpCommandProcessor
    service: CloudMqttService

    def start(self) -> None:
        self.service.start()

    def send(self, payload: str | bytes, *, retain: bool = False) -> None:
        encoded = payload.encode() if isinstance(payload, str) else payload
        self.transport.simulate_message(
            ReceivedMqttMessage(self.topics.pump_command(), encoded, 1, retain)
        )

    def acknowledgements(self) -> list[CommandAcknowledgement]:
        return [
            CommandAcknowledgement.from_json(publication.payload)
            for publication in self.transport.publications
            if "/acks/" in publication.topic
        ]


def make_harness(
    *,
    pump: FakePump | None = None,
    scheduler: FakeScheduler | None = None,
    transport: FakeMqttTransport | None = None,
    logger: logging.Logger | None = None,
) -> Harness:
    mqtt_transport = transport or FakeMqttTransport()
    fake_pump = pump or FakePump()
    fake_scheduler = scheduler or FakeScheduler()
    topics = TopicBuilder(FARM_ID, DEVICE_ID)
    identifiers = count(100)
    publisher = MqttAcknowledgementPublisher(mqtt_transport, topics, logger=logger)
    handler = PumpCommandHandler(
        SafePumpController(fake_pump, fake_scheduler),
        PumpSafetyConfig(FARM_ID, DEVICE_ID, 120),
        clock=lambda: NOW,
        acknowledgement_id_factory=lambda: UUID(int=next(identifiers)),
        acknowledgement_sink=publisher.publish,
        logger=logger,
    )
    processor = MqttPumpCommandProcessor(
        handler,
        publisher,
        topics,
        clock=lambda: NOW,
        acknowledgement_id_factory=lambda: UUID(int=next(identifiers)),
        logger=logger,
    )
    service = CloudMqttService(
        mqtt_transport,
        TelemetryMapper(FARM_ID, DEVICE_ID),
        topics,
        FakeDeviceStatusSource(DeviceRuntimeStatus(False, DeviceHealth.HEALTHY, 0, "0.0.0")),
        command_message_handler=processor.process,
        clock=lambda: NOW,
        message_id_factory=lambda: UUID(int=next(identifiers)),
    )
    return Harness(mqtt_transport, fake_pump, fake_scheduler, topics, processor, service)


def test_subscribes_exact_command_topic_at_qos_one_and_restores_after_reconnect() -> None:
    harness = make_harness()
    harness.start()

    assert harness.transport.subscriptions == [(harness.topics.pump_command(), 1)]

    harness.transport.simulate_disconnect()
    with pytest.raises(RuntimeError, match="while disconnected"):
        harness.send(command().to_json())
    harness.transport.simulate_reconnect()

    assert harness.transport.subscriptions == [
        (harness.topics.pump_command(), 1),
        (harness.topics.pump_command(), 1),
    ]


def test_valid_on_flows_from_mqtt_to_fake_pump_and_correlated_acknowledgements() -> None:
    harness = make_harness()
    expected = command()
    harness.start()

    harness.send(expected.to_json())

    accepted = harness.acknowledgements()
    assert len(accepted) == 1
    assert accepted[0].command_id == expected.command_id
    assert accepted[0].status is AcknowledgementStatus.ACCEPTED
    assert harness.pump.calls.count("turn_on") == 1
    publication = next(item for item in harness.transport.publications if "/acks/" in item.topic)
    assert publication.topic == harness.topics.acknowledgement(expected.command_id)
    assert publication.qos == 1
    assert publication.retain is False

    harness.scheduler.fire_next()

    assert [ack.status for ack in harness.acknowledgements()] == [
        AcknowledgementStatus.ACCEPTED,
        AcknowledgementStatus.COMPLETED,
    ]
    assert harness.pump.active is False


def test_automatic_stop_failure_publishes_failed_ack() -> None:
    harness = make_harness(pump=FakePump({"turn_off": [RuntimeError("synthetic stop failure")]}))
    harness.start()
    harness.send(command().to_json())

    harness.scheduler.fire_next()

    assert [ack.status for ack in harness.acknowledgements()] == [
        AcknowledgementStatus.ACCEPTED,
        AcknowledgementStatus.FAILED,
    ]
    assert harness.acknowledgements()[-1].reason_code == "pump_actuation_failed"


def test_valid_off_stops_running_fake_pump_and_publishes_completed_only() -> None:
    harness = make_harness()
    harness.start()
    harness.send(command().to_json())
    off = command(command_id=UUID(int=11), action=PumpAction.OFF)

    harness.send(off.to_json())

    matching = [ack for ack in harness.acknowledgements() if ack.command_id == off.command_id]
    assert [ack.status for ack in matching] == [AcknowledgementStatus.COMPLETED]
    assert harness.pump.active is False


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("farm_id", UUID(int=91), "wrong_farm"),
        ("device_id", UUID(int=92), "wrong_device"),
    ],
)
def test_wrong_target_is_rejected_without_actuation(field: str, value: UUID, reason: str) -> None:
    harness = make_harness()
    harness.start()
    targeted = replace(command(), **{field: value})

    harness.send(targeted.to_json())

    assert harness.acknowledgements()[-1].reason_code == reason
    assert harness.pump.calls == []


@pytest.mark.parametrize(
    ("issued_at", "expires_at", "reason"),
    [
        (NOW - timedelta(minutes=1), NOW, "expired_command"),
        (NOW + timedelta(seconds=1), NOW + timedelta(seconds=30), "future_command"),
    ],
)
def test_timing_decisions_reach_existing_handler(
    issued_at: datetime, expires_at: datetime, reason: str
) -> None:
    harness = make_harness()
    harness.start()
    timed = command(issued_at=issued_at, expires_at=expires_at)

    harness.send(timed.to_json())

    assert harness.acknowledgements()[-1].reason_code == reason
    assert harness.pump.calls == []


@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: payload.__setitem__("schema_version", 2),
        lambda payload: payload.__setitem__("action", "toggle"),
        lambda payload: payload.__setitem__("duration_seconds", 0),
        lambda payload: payload.pop("requested_by"),
    ],
)
def test_invalid_but_correlatable_command_publishes_invalid_command(
    mutation: object,
) -> None:
    harness = make_harness()
    harness.start()
    payload = command().to_dict()
    assert callable(mutation)
    mutation(payload)

    harness.send(json.dumps(payload))

    acknowledgement = harness.acknowledgements()[-1]
    assert acknowledgement.command_id == command().command_id
    assert acknowledgement.status is AcknowledgementStatus.REJECTED
    assert acknowledgement.reason_code == "invalid_command"
    assert harness.pump.calls == []


@pytest.mark.parametrize(
    "payload",
    [
        b"not-json",
        b'{"schema_version":1}',
        b'{"command_id":"not-a-uuid"}',
    ],
)
def test_uncorrelatable_command_has_no_ack_or_actuation(payload: bytes) -> None:
    harness = make_harness()
    harness.start()

    harness.send(payload)

    assert harness.acknowledgements() == []
    assert harness.pump.calls == []


def test_logs_do_not_include_untrusted_payload(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("agrimind.test.mqtt-command")
    caplog.set_level(logging.WARNING, logger=logger.name)
    harness = make_harness(logger=logger)
    harness.start()

    harness.send(b'{"password":"do-not-log-this"}')  # pragma: allowlist secret

    assert "mqtt_pump_command_rejected" in caplog.text
    assert "do-not-log-this" not in caplog.text


def test_duplicate_replays_ack_without_second_actuation() -> None:
    harness = make_harness()
    payload = command().to_json()
    harness.start()

    harness.send(payload)
    harness.send(payload)

    acknowledgements = harness.acknowledgements()
    assert len(acknowledgements) == 2
    assert acknowledgements[1] == acknowledgements[0]
    assert harness.pump.calls.count("turn_on") == 1
    assert len(harness.scheduler.calls) == 1


def test_same_id_with_different_content_is_rejected_as_conflict() -> None:
    harness = make_harness()
    harness.start()
    harness.send(command(duration_seconds=10).to_json())

    harness.send(command(duration_seconds=11).to_json())

    assert harness.acknowledgements()[-1].reason_code == "command_id_conflict"
    assert harness.pump.calls.count("turn_on") == 1


def test_pump_and_scheduler_failures_are_published_safely() -> None:
    pump_failure = make_harness(
        pump=FakePump({"turn_on": [RuntimeError("synthetic pump failure")]})
    )
    pump_failure.start()
    pump_failure.send(command().to_json())
    assert pump_failure.acknowledgements()[-1].reason_code == "pump_actuation_failed"

    scheduler_failure = make_harness(
        scheduler=FakeScheduler(failure=RuntimeError("synthetic scheduler failure"))
    )
    scheduler_failure.start()
    scheduler_failure.send(command().to_json())
    assert scheduler_failure.acknowledgements()[-1].reason_code == "scheduler_failed"
    assert scheduler_failure.pump.active is False


def test_ack_publish_failure_does_not_bypass_safety_or_escape_callback() -> None:
    transport = FakeMqttTransport(fail_publish_at={2})
    harness = make_harness(transport=transport)
    harness.start()  # online status is publish attempt one

    harness.send(command().to_json())

    assert harness.pump.active is True
    assert harness.pump.calls.count("turn_on") == 1
    assert harness.acknowledgements() == []


def test_completion_while_disconnected_stops_pump_without_publishing() -> None:
    harness = make_harness()
    harness.start()
    harness.send(command().to_json())
    harness.transport.simulate_disconnect()

    harness.scheduler.fire_next()

    assert harness.pump.active is False
    assert [ack.status for ack in harness.acknowledgements()] == [AcknowledgementStatus.ACCEPTED]


def test_retained_or_wrong_topic_command_never_actuates() -> None:
    harness = make_harness()
    harness.start()
    harness.send(command().to_json(), retain=True)
    harness.processor.process(
        ReceivedMqttMessage("agrimind/v1/unexpected", command().to_json().encode(), 1, False)
    )

    assert harness.acknowledgements() == []
    assert harness.pump.calls == []


def test_application_command_path_has_no_paho_or_gpio_dependency() -> None:
    source = Path("edge/src/agrimind_edge/application/mqtt_commands.py").read_text(encoding="utf-8")

    assert "paho" not in source.lower()
    assert "GPIO" not in source
    assert "RPi" not in source
