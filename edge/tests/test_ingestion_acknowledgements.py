from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from agrimind_edge.adapters.persistence import SqliteEventOutboxStore
from agrimind_edge.application import IngestionAcknowledgementProcessor
from agrimind_edge.contracts import IngestionAcknowledgement, Telemetry, TopicBuilder
from agrimind_edge.contracts.enums import (
    IngestionAcknowledgementStatus,
    TelemetryMetric,
)
from agrimind_edge.domain.mqtt import MqttPublication, ReceivedMqttMessage
from agrimind_edge.domain.persistence import EdgeEvent, EnqueueResult

NOW = datetime(2026, 9, 23, 12, tzinfo=UTC)
FARM = UUID("11111111-1111-4111-8111-111111111111")
DEVICE = UUID("22222222-2222-4222-8222-222222222222")
MESSAGE = UUID("33333333-3333-4333-8333-333333333333")


def setup_store(path: Path) -> tuple[SqliteEventOutboxStore, Telemetry, TopicBuilder]:
    store = SqliteEventOutboxStore(path)
    store.initialize()
    telemetry = Telemetry(MESSAGE, FARM, DEVICE, TelemetryMetric.TEMPERATURE, 22.5, "°C", NOW)
    topics = TopicBuilder(FARM, DEVICE)
    publication = MqttPublication(topics.telemetry(telemetry.metric), telemetry.to_json(), 1, False)
    store.enqueue(EdgeEvent.from_telemetry(telemetry), publication, NOW)
    store.mark_broker_accepted(MESSAGE, NOW)
    return store, telemetry, topics


def message(
    acknowledgement: IngestionAcknowledgement,
    topics: TopicBuilder,
    *,
    topic_message_id: UUID = MESSAGE,
) -> ReceivedMqttMessage:
    return ReceivedMqttMessage(
        topics.ingestion_acknowledgement(topic_message_id),
        acknowledgement.to_json().encode(),
        1,
        False,
    )


def test_persisted_and_duplicate_receipts_converge_idempotently(tmp_path: Path) -> None:
    store, telemetry, topics = setup_store(tmp_path / "edge.sqlite3")
    processor = IngestionAcknowledgementProcessor(store, topics)
    persisted = IngestionAcknowledgement(
        MESSAGE,
        FARM,
        DEVICE,
        "telemetry",
        IngestionAcknowledgementStatus.PERSISTED,
        NOW,
    )

    processor.process(message(persisted, topics))
    processor.process(message(persisted, topics))

    publication = MqttPublication(topics.telemetry(telemetry.metric), telemetry.to_json(), 1, False)
    assert store.pending(limit=10) == ()
    assert (
        store.enqueue(EdgeEvent.from_telemetry(telemetry), publication, NOW)
        is EnqueueResult.CLOUD_CONFIRMED
    )


def test_receipt_racing_broker_state_update_remains_terminal(tmp_path: Path) -> None:
    store, telemetry, topics = setup_store(tmp_path / "edge.sqlite3")
    acknowledgement = IngestionAcknowledgement(
        MESSAGE,
        FARM,
        DEVICE,
        "telemetry",
        IngestionAcknowledgementStatus.PERSISTED,
        NOW,
    )

    assert store.apply_ingestion_acknowledgement(acknowledgement) is True
    store.record_attempt(MESSAGE, NOW)
    store.mark_broker_accepted(MESSAGE, NOW)

    publication = MqttPublication(
        topics.telemetry(telemetry.metric), telemetry.to_json(), 1, False
    )
    assert (
        store.enqueue(EdgeEvent.from_telemetry(telemetry), publication, NOW)
        is EnqueueResult.CLOUD_CONFIRMED
    )


def test_rejection_is_terminal_and_conflicting_receipt_does_not_overwrite(
    tmp_path: Path,
) -> None:
    store, telemetry, topics = setup_store(tmp_path / "edge.sqlite3")
    processor = IngestionAcknowledgementProcessor(store, topics)
    rejected = IngestionAcknowledgement(
        MESSAGE,
        FARM,
        DEVICE,
        "telemetry",
        IngestionAcknowledgementStatus.REJECTED,
        NOW,
        "stale_message",
    )
    persisted = IngestionAcknowledgement(
        MESSAGE,
        FARM,
        DEVICE,
        "telemetry",
        IngestionAcknowledgementStatus.PERSISTED,
        NOW,
    )

    processor.process(message(rejected, topics))
    processor.process(message(persisted, topics))

    publication = MqttPublication(topics.telemetry(telemetry.metric), telemetry.to_json(), 1, False)
    assert store.pending(limit=10) == ()
    assert (
        store.enqueue(EdgeEvent.from_telemetry(telemetry), publication, NOW)
        is EnqueueResult.REJECTED
    )


def test_wrong_topic_target_or_unknown_message_cannot_mutate_event(tmp_path: Path) -> None:
    store, telemetry, topics = setup_store(tmp_path / "edge.sqlite3")
    processor = IngestionAcknowledgementProcessor(store, topics)
    acknowledgement = IngestionAcknowledgement(
        MESSAGE,
        FARM,
        DEVICE,
        "telemetry",
        IngestionAcknowledgementStatus.PERSISTED,
        NOW,
    )

    processor.process(message(acknowledgement, topics, topic_message_id=UUID(int=9)))
    wrong_target = IngestionAcknowledgement(
        MESSAGE,
        UUID(int=8),
        DEVICE,
        "telemetry",
        IngestionAcknowledgementStatus.PERSISTED,
        NOW,
    )
    processor.process(message(wrong_target, topics))
    unknown_id = UUID(int=10)
    unknown = IngestionAcknowledgement(
        unknown_id,
        FARM,
        DEVICE,
        "telemetry",
        IngestionAcknowledgementStatus.PERSISTED,
        NOW,
    )
    processor.process(message(unknown, topics, topic_message_id=unknown_id))

    assert len(store.pending(limit=10)) == 1
    publication = MqttPublication(topics.telemetry(telemetry.metric), telemetry.to_json(), 1, False)
    assert (
        store.enqueue(EdgeEvent.from_telemetry(telemetry), publication, NOW)
        is EnqueueResult.BROKER_ACCEPTED
    )
