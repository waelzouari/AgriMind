from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from agrimind_ingestion.application.acknowledgements import (
    IngestionAcknowledgementFactory,
)
from agrimind_ingestion.domain import IngestionOutcome, IngestionResult, MessageKind

from agrimind_edge.adapters.fake import FakeMqttTransport
from agrimind_edge.config import RuntimeConfig
from agrimind_edge.contracts import IngestionAcknowledgement, Telemetry
from agrimind_edge.domain.mqtt import MqttPublication, ReceivedMqttMessage
from agrimind_edge.domain.persistence import EdgeEvent, EnqueueResult
from agrimind_edge.entrypoints.offline_sync_validate import build_offline_sync_runtime

NOW = datetime(2026, 9, 23, 12, tzinfo=UTC)


def config(tmp_path: Path) -> RuntimeConfig:
    return RuntimeConfig.from_environment(
        {
            "AGRIMIND_FARM_ID": "11111111-1111-4111-8111-111111111111",
            "AGRIMIND_DEVICE_ID": "22222222-2222-4222-8222-222222222222",
            "AGRIMIND_MQTT_HOST": "mqtt.example.invalid",
            "AGRIMIND_MQTT_CA_FILE": "/absolute/ca.pem",
            "AGRIMIND_MQTT_USERNAME": "device-user",  # pragma: allowlist secret
            "AGRIMIND_MQTT_PASSWORD": "device-password",  # pragma: allowlist secret
            "AGRIMIND_SQLITE_PATH": str(tmp_path / "edge.sqlite3"),
        }
    )


def test_offline_replay_and_cloud_duplicate_receipt_converge_with_same_identity(
    tmp_path: Path,
) -> None:
    transport = FakeMqttTransport(auto_connect=False)
    runtime = build_offline_sync_runtime(
        config(tmp_path), transport=transport, drain_submitter=lambda callback: callback()
    )
    runtime.service.start()

    result = runtime.service.publish_snapshot(runtime.sensors.capture())
    pending_before = runtime.store.pending(limit=10)
    assert result.published == 0
    assert len(pending_before) == 4
    original_ids = [entry.event.event_id for entry in pending_before]
    original_payloads = [entry.publication.payload for entry in pending_before]

    transport.simulate_reconnect()
    replayed = [item for item in transport.publications if "/telemetry/" in item.topic]
    assert [Telemetry.from_json(item.payload).message_id for item in replayed] == original_ids
    assert [item.payload for item in replayed] == original_payloads

    first = Telemetry.from_json(replayed[0].payload)
    factory = IngestionAcknowledgementFactory(clock=lambda: NOW)
    inserted = IngestionResult(
        IngestionOutcome.INSERTED,
        "inserted",
        first.message_id,
        first.device_id,
        first.farm_id,
        MessageKind.TELEMETRY,
    )
    publication = factory.create(inserted)
    assert publication is not None
    transport.simulate_message(
        ReceivedMqttMessage(publication.topic, publication.payload.encode(), 1, False)
    )

    stored_publication = MqttPublication(
        runtime.topics.telemetry(first.metric), first.to_json(), 1, False
    )
    assert (
        runtime.store.enqueue(
            EdgeEvent.from_telemetry(first), stored_publication, datetime.now(UTC)
        )
        is EnqueueResult.CLOUD_CONFIRMED
    )

    duplicate = factory.create(
        IngestionResult(
            IngestionOutcome.DUPLICATE,
            "duplicate",
            first.message_id,
            first.device_id,
            first.farm_id,
            MessageKind.TELEMETRY,
        )
    )
    assert duplicate is not None
    acknowledgement = IngestionAcknowledgement.from_json(duplicate.payload)
    assert acknowledgement.message_id == first.message_id
    transport.simulate_message(
        ReceivedMqttMessage(duplicate.topic, duplicate.payload.encode(), 1, False)
    )
    assert original_ids[0] == first.message_id
