from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest

from agrimind_edge.adapters.fake import FakeMqttTransport
from agrimind_edge.adapters.persistence import SqliteEventOutboxStore
from agrimind_edge.adapters.persistence.migrations import MIGRATIONS
from agrimind_edge.application.outbox_service import OutboxService
from agrimind_edge.application.persistence_ports import PersistenceConflict, PersistenceError
from agrimind_edge.contracts import (
    CommandAcknowledgement,
    IngestionAcknowledgement,
    PumpCommand,
    Telemetry,
)
from agrimind_edge.contracts.enums import (
    AcknowledgementStatus,
    IngestionAcknowledgementStatus,
    PumpAction,
    TelemetryMetric,
)
from agrimind_edge.domain.mqtt import MqttPublication
from agrimind_edge.domain.persistence import EdgeEvent, EnqueueResult, ProcessedCommandRecord

NOW = datetime(2026, 9, 23, 12, tzinfo=UTC)
FARM_ID = UUID("11111111-1111-4111-8111-111111111111")
DEVICE_ID = UUID("22222222-2222-4222-8222-222222222222")
USER_ID = UUID("33333333-3333-4333-8333-333333333333")


def telemetry(number: int, occurred_at: datetime = NOW) -> Telemetry:
    return Telemetry(
        UUID(int=number),
        FARM_ID,
        DEVICE_ID,
        TelemetryMetric.TEMPERATURE,
        24.5,
        "°C",
        occurred_at,
    )


def publication(item: Telemetry) -> MqttPublication:
    return MqttPublication("agrimind/v1/test", item.to_json(), 1, False)


def ingestion_ack(
    item: Telemetry,
    status: IngestionAcknowledgementStatus = IngestionAcknowledgementStatus.PERSISTED,
    *,
    reason_code: str | None = None,
) -> IngestionAcknowledgement:
    return IngestionAcknowledgement(
        item.message_id,
        item.farm_id,
        item.device_id,
        "telemetry",
        status,
        NOW,
        reason_code,
    )


def test_schema_is_idempotent_and_pending_survives_restart(tmp_path: Path) -> None:
    path = tmp_path / "edge.sqlite3"
    item = telemetry(1)
    event = EdgeEvent.from_telemetry(item)
    first = SqliteEventOutboxStore(path)
    first.initialize()
    assert first.enqueue(event, publication(item), NOW) is EnqueueResult.CREATED
    first.close()

    second = SqliteEventOutboxStore(path)
    second.initialize()
    assert second.enqueue(event, publication(item), NOW) is EnqueueResult.PENDING
    assert second.pending(limit=10)[0].event == event


def test_duplicate_is_idempotent_but_changed_content_conflicts(tmp_path: Path) -> None:
    store = SqliteEventOutboxStore(tmp_path / "edge.sqlite3")
    store.initialize()
    item = telemetry(2)
    event = EdgeEvent.from_telemetry(item)
    assert store.enqueue(event, publication(item), NOW) is EnqueueResult.CREATED
    assert store.enqueue(event, publication(item), NOW) is EnqueueResult.PENDING
    changed = MqttPublication("agrimind/v1/changed", item.to_json(), 1, False)
    with pytest.raises(PersistenceConflict):
        store.enqueue(event, changed, NOW)


def test_pending_order_is_occurrence_time_then_event_id(tmp_path: Path) -> None:
    store = SqliteEventOutboxStore(tmp_path / "edge.sqlite3")
    store.initialize()
    later = telemetry(30, NOW)
    higher_id = telemetry(32, NOW - timedelta(minutes=1))
    lower_id = telemetry(31, NOW - timedelta(minutes=1))
    for item in (later, higher_id, lower_id):
        store.enqueue(EdgeEvent.from_telemetry(item), publication(item), NOW)

    assert [entry.event.event_id for entry in store.pending(limit=10)] == [
        lower_id.message_id,
        higher_id.message_id,
        later.message_id,
    ]


def test_puback_is_required_before_delivery_and_retry(tmp_path: Path) -> None:
    store = SqliteEventOutboxStore(tmp_path / "edge.sqlite3")
    transport = FakeMqttTransport(unconfirmed_publish_at={1})
    transport.connect()
    outbox = OutboxService(store, transport, clock=lambda: NOW)
    outbox.initialize()
    item = telemetry(3)
    event = EdgeEvent.from_telemetry(item)

    assert outbox.submit(event, publication(item), attempt_now=True) is False
    assert len(store.pending(limit=10)) == 1
    outbox.drain()
    assert len(store.pending(limit=10)) == 1
    assert store.enqueue(event, publication(item), NOW) is EnqueueResult.BROKER_ACCEPTED
    assert store.apply_ingestion_acknowledgement(ingestion_ack(item)) is True
    assert store.pending(limit=10) == ()
    assert store.enqueue(event, publication(item), NOW) is EnqueueResult.CLOUD_CONFIRMED


def test_publish_failure_remains_pending_for_retry(tmp_path: Path) -> None:
    store = SqliteEventOutboxStore(tmp_path / "edge.sqlite3")
    transport = FakeMqttTransport(fail_publish_at={1})
    transport.connect()
    outbox = OutboxService(store, transport, clock=lambda: NOW)
    outbox.initialize()
    item = telemetry(33)

    assert (
        outbox.submit(EdgeEvent.from_telemetry(item), publication(item), attempt_now=True) is False
    )
    assert len(store.pending(limit=10)) == 1
    outbox.drain()
    assert len(store.pending(limit=10)) == 1


class MarkDeliveryFailureStore(SqliteEventOutboxStore):
    def mark_broker_accepted(self, event_id: UUID, accepted_at: datetime) -> None:
        raise PersistenceError("simulated crash window")


def test_puback_before_sqlite_mark_is_republished_after_restart(tmp_path: Path) -> None:
    path = tmp_path / "edge.sqlite3"
    failing_store = MarkDeliveryFailureStore(path)
    transport = FakeMqttTransport()
    transport.connect()
    outbox = OutboxService(failing_store, transport, clock=lambda: NOW)
    outbox.initialize()
    item = telemetry(34)
    assert (
        outbox.submit(EdgeEvent.from_telemetry(item), publication(item), attempt_now=True) is False
    )
    failing_store.close()

    restarted_store = SqliteEventOutboxStore(path)
    restarted_outbox = OutboxService(restarted_store, transport, clock=lambda: NOW)
    restarted_outbox.initialize()
    restarted_outbox.drain()

    assert len(transport.publications) == 2
    assert len(restarted_store.pending(limit=10)) == 1


def test_retention_prunes_pending_and_delivered_at_24_hours(tmp_path: Path) -> None:
    store = SqliteEventOutboxStore(tmp_path / "edge.sqlite3")
    store.initialize()
    old_pending = telemetry(4, NOW - timedelta(hours=24))
    old_delivered = telemetry(5, NOW - timedelta(hours=25))
    recent = telemetry(6, NOW - timedelta(hours=23, minutes=59))
    for item in (old_pending, old_delivered, recent):
        store.enqueue(EdgeEvent.from_telemetry(item), publication(item), NOW)
    store.mark_broker_accepted(old_delivered.message_id, NOW)
    store.apply_ingestion_acknowledgement(ingestion_ack(old_delivered))

    result = store.prune(NOW - timedelta(hours=24), NOW)

    assert (result.pending_events, result.delivered_events) == (1, 1)
    assert [entry.event.event_id for entry in store.pending(limit=10)] == [recent.message_id]


@pytest.mark.parametrize(
    ("age", "survives"),
    [
        (timedelta(minutes=1), True),
        (timedelta(hours=1), True),
        (timedelta(hours=23), True),
        (timedelta(hours=23, minutes=59, seconds=59), True),
        (timedelta(hours=24), False),
        (timedelta(hours=25), False),
    ],
)
def test_retention_boundary_is_deterministic(
    tmp_path: Path, age: timedelta, survives: bool
) -> None:
    store = SqliteEventOutboxStore(tmp_path / "edge.sqlite3")
    store.initialize()
    item = telemetry(40, NOW - age)
    store.enqueue(EdgeEvent.from_telemetry(item), publication(item), NOW)

    store.prune(NOW - timedelta(hours=24), NOW)

    assert bool(store.pending(limit=10)) is survives


def test_rejected_terminal_event_is_not_retried_and_is_purged_normally(
    tmp_path: Path,
) -> None:
    store = SqliteEventOutboxStore(tmp_path / "edge.sqlite3")
    store.initialize()
    item = telemetry(42, NOW - timedelta(hours=25))
    event = EdgeEvent.from_telemetry(item)
    mqtt = publication(item)
    store.enqueue(event, mqtt, NOW)
    store.apply_ingestion_acknowledgement(
        ingestion_ack(
            item,
            IngestionAcknowledgementStatus.REJECTED,
            reason_code="stale_message",
        )
    )

    assert store.pending(limit=10) == ()
    result = store.prune(NOW - timedelta(hours=24), NOW)
    assert result.delivered_events == 1
    assert store.enqueue(event, mqtt, NOW) is EnqueueResult.CREATED


def test_agm008_delivered_rows_migrate_conservatively_to_broker_accepted(
    tmp_path: Path,
) -> None:
    path = tmp_path / "edge.sqlite3"
    item = telemetry(41)
    event = EdgeEvent.from_telemetry(item)
    mqtt = publication(item)
    connection = sqlite3.connect(path)
    connection.executescript(MIGRATIONS[0])
    connection.execute(
        "CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    connection.execute("INSERT INTO schema_migrations VALUES (1, ?)", (NOW.isoformat(),))
    connection.execute(
        "INSERT INTO edge_events VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            str(event.event_id),
            event.event_type.value,
            str(event.farm_id),
            str(event.device_id),
            "2026-09-23T12:00:00.000Z",
            event.payload,
            "2026-09-23T12:00:00.000Z",
        ),
    )
    connection.execute(
        "INSERT INTO outbox VALUES (?, ?, ?, ?, ?, 'delivered', 1, ?, ?, ?)",
        (
            str(event.event_id),
            mqtt.topic,
            mqtt.payload,
            mqtt.qos,
            int(mqtt.retain),
            "2026-09-23T12:00:00.000Z",
            "2026-09-23T12:00:00.000Z",
            "2026-09-23T12:00:00.000Z",
        ),
    )
    connection.commit()
    connection.close()

    store = SqliteEventOutboxStore(path)
    store.initialize()

    assert store.enqueue(event, mqtt, NOW) is EnqueueResult.BROKER_ACCEPTED
    assert len(store.pending(limit=10)) == 1


def test_processed_command_survives_restart_without_replay(tmp_path: Path) -> None:
    path = tmp_path / "edge.sqlite3"
    command = PumpCommand(
        UUID(int=7),
        FARM_ID,
        DEVICE_ID,
        PumpAction.OFF,
        NOW - timedelta(seconds=1),
        NOW + timedelta(minutes=1),
        USER_ID,
    )
    acknowledgement = CommandAcknowledgement(
        UUID(int=8),
        command.command_id,
        FARM_ID,
        DEVICE_ID,
        AcknowledgementStatus.COMPLETED,
        NOW,
        pump_state=False,
    )
    record = ProcessedCommandRecord.from_command(command, acknowledgement, NOW)
    first = SqliteEventOutboxStore(path)
    first.initialize()
    first.save_processed_command(record)
    first.close()

    second = SqliteEventOutboxStore(path)
    second.initialize()
    assert second.get_processed_command(command.command_id) == record
    assert second.pending(limit=10) == ()


def test_corrupt_database_fails_as_persistence_error(tmp_path: Path) -> None:
    path = tmp_path / "edge.sqlite3"
    path.write_text("not sqlite", encoding="utf-8")
    with pytest.raises(PersistenceError, match="initialization failed"):
        SqliteEventOutboxStore(path).initialize()


def test_locked_database_fails_without_deleting_it(tmp_path: Path) -> None:
    path = tmp_path / "edge.sqlite3"
    store = SqliteEventOutboxStore(path, busy_timeout_ms=1)
    store.initialize()
    lock = sqlite3.connect(path)
    lock.execute("BEGIN EXCLUSIVE")
    item = telemetry(35)
    try:
        with pytest.raises(PersistenceError, match="enqueue failed"):
            store.enqueue(EdgeEvent.from_telemetry(item), publication(item), NOW)
    finally:
        lock.rollback()
        lock.close()
    assert path.exists()


def test_unwritable_database_location_fails_without_recovery(tmp_path: Path) -> None:
    directory = tmp_path / "missing" / "nested"
    with pytest.raises(PersistenceError, match="initialization failed"):
        SqliteEventOutboxStore(directory / "edge.sqlite3").initialize()
    assert not directory.exists()


def test_read_only_database_fails_without_recreating_it(tmp_path: Path) -> None:
    directory = tmp_path / "readonly"
    directory.mkdir()
    path = directory / "edge.sqlite3"
    writable = SqliteEventOutboxStore(path)
    writable.initialize()
    writable.close()
    path.chmod(0o444)
    directory.chmod(0o555)
    readonly = SqliteEventOutboxStore(path, busy_timeout_ms=1)
    item = telemetry(36)
    try:
        try:
            readonly.initialize()
        except PersistenceError:
            pass
        else:
            with pytest.raises(PersistenceError):
                readonly.enqueue(EdgeEvent.from_telemetry(item), publication(item), NOW)
    finally:
        readonly.close()
        directory.chmod(0o755)
        path.chmod(0o644)
    assert path.exists()


class UnavailableStore:
    def initialize(self) -> None:
        raise PersistenceError("unavailable")

    def enqueue(self, *args: object) -> EnqueueResult:
        raise AssertionError("unreachable")

    def pending(self, *, limit: int) -> tuple[object, ...]:
        raise AssertionError("unreachable")

    def record_attempt(self, *args: object) -> None:
        raise AssertionError("unreachable")

    def mark_delivered(self, *args: object) -> None:
        raise AssertionError("unreachable")

    def prune(self, *args: object) -> object:
        raise AssertionError("unreachable")

    def close(self) -> None:
        pass


def test_sqlite_failure_uses_direct_best_effort_when_mqtt_is_available() -> None:
    transport = FakeMqttTransport()
    transport.connect()
    outbox = OutboxService(UnavailableStore(), transport, clock=lambda: NOW)  # type: ignore[arg-type]
    item = telemetry(9)

    assert (
        outbox.submit(EdgeEvent.from_telemetry(item), publication(item), attempt_now=True) is True
    )
    assert transport.publications == [publication(item)]


def test_sqlite_and_mqtt_failure_does_not_raise() -> None:
    transport = FakeMqttTransport(auto_connect=False)
    outbox = OutboxService(UnavailableStore(), transport, clock=lambda: NOW)  # type: ignore[arg-type]
    item = telemetry(10)

    assert (
        outbox.submit(EdgeEvent.from_telemetry(item), publication(item), attempt_now=False) is False
    )
