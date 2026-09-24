"""SQLite implementation of the local event store, outbox, and command receipts."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from threading import RLock
from uuid import UUID

from agrimind_edge.application.persistence_ports import (
    PersistenceConflict,
    PersistenceError,
)
from agrimind_edge.contracts import CommandAcknowledgement, IngestionAcknowledgement
from agrimind_edge.contracts.enums import IngestionAcknowledgementStatus
from agrimind_edge.contracts.validation import format_utc_timestamp, parse_utc_timestamp
from agrimind_edge.domain.mqtt import MqttPublication
from agrimind_edge.domain.persistence import (
    EdgeEvent,
    EdgeEventType,
    EnqueueResult,
    OutboxEntry,
    ProcessedCommandRecord,
    PruneResult,
)
from agrimind_edge.domain.schedules import (
    IrrigationSchedule,
    OccurrenceStatus,
    ScheduleOccurrence,
    ScheduleSummary,
    command_id_for,
    occurrence_id_for,
)

from .migrations import MIGRATIONS


class SqliteEventOutboxStore:
    def __init__(self, database_path: Path | str, *, busy_timeout_ms: int = 5_000) -> None:
        if busy_timeout_ms < 1:
            raise ValueError("SQLite busy timeout must be positive")
        self._database_path = str(database_path)
        self._busy_timeout_ms = busy_timeout_ms
        self._connection: sqlite3.Connection | None = None
        self._lock = RLock()

    def initialize(self) -> None:
        with self._lock:
            if self._connection is not None:
                return
            try:
                connection = sqlite3.connect(
                    self._database_path,
                    timeout=self._busy_timeout_ms / 1_000,
                    check_same_thread=False,
                )
                connection.row_factory = sqlite3.Row
                connection.execute("PRAGMA foreign_keys = ON")
                connection.execute(f"PRAGMA busy_timeout = {self._busy_timeout_ms}")
                if self._database_path != ":memory:":
                    connection.execute("PRAGMA journal_mode = WAL")
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS schema_migrations ("
                    "version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
                )
                applied = {
                    row[0]
                    for row in connection.execute(
                        "SELECT version FROM schema_migrations ORDER BY version"
                    )
                }
                if any(version < 1 or version > len(MIGRATIONS) for version in applied):
                    raise PersistenceError("SQLite schema version is unsupported")
                for version, migration in enumerate(MIGRATIONS, start=1):
                    if version in applied:
                        continue
                    connection.executescript(
                        "BEGIN IMMEDIATE;\n"
                        f"{migration}\n"
                        "INSERT INTO schema_migrations(version, applied_at) "
                        f"VALUES ({version}, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'));\n"
                        "COMMIT;"
                    )
                self._connection = connection
            except (OSError, sqlite3.DatabaseError, PersistenceError) as error:
                if "connection" in locals():
                    connection.close()
                if isinstance(error, PersistenceError):
                    raise
                raise PersistenceError("SQLite initialization failed") from error

    def enqueue(
        self,
        event: EdgeEvent,
        publication: MqttPublication,
        created_at: datetime,
    ) -> EnqueueResult:
        created = format_utc_timestamp(created_at, "created_at")
        immutable = (
            event.event_type.value,
            str(event.farm_id),
            str(event.device_id),
            format_utc_timestamp(event.occurred_at, "occurred_at"),
            event.payload,
            publication.topic,
            publication.payload,
            publication.qos,
            int(publication.retain),
        )
        with self._lock:
            connection = self._require_connection()
            try:
                existing = connection.execute(
                    """
                    SELECT e.event_type, e.farm_id, e.device_id, e.occurred_at,
                           e.payload, o.topic, o.payload, o.qos, o.retain, o.state
                    FROM edge_events e JOIN outbox o USING(event_id)
                    WHERE e.event_id = ?
                    """,
                    (str(event.event_id),),
                ).fetchone()
                if existing is not None:
                    if tuple(existing[:9]) != immutable:
                        raise PersistenceConflict(
                            "event identity already exists with different content"
                        )
                    return EnqueueResult(existing["state"])
                with connection:
                    connection.execute(
                        """
                        INSERT INTO edge_events(
                            event_id, event_type, farm_id, device_id,
                            occurred_at, payload, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (str(event.event_id), *immutable[:5], created),
                    )
                    connection.execute(
                        """
                        INSERT INTO outbox(
                            event_id, topic, payload, qos, retain, state,
                            attempt_count, created_at
                        ) VALUES (?, ?, ?, ?, ?, 'pending', 0, ?)
                        """,
                        (str(event.event_id), *immutable[5:], created),
                    )
                return EnqueueResult.CREATED
            except PersistenceConflict:
                raise
            except sqlite3.DatabaseError as error:
                raise PersistenceError("SQLite event enqueue failed") from error

    def create_schedule(self, schedule: IrrigationSchedule) -> None:
        values = (
            str(schedule.schedule_id),
            str(schedule.farm_id),
            str(schedule.device_id),
            format_utc_timestamp(schedule.scheduled_for, "scheduled_for"),
            schedule.duration_seconds,
            int(schedule.enabled),
            format_utc_timestamp(schedule.created_at, "created_at"),
            format_utc_timestamp(schedule.updated_at, "updated_at"),
            format_utc_timestamp(schedule.disabled_at, "disabled_at")
            if schedule.disabled_at is not None
            else None,
        )
        with self._lock:
            connection = self._require_connection()
            try:
                with connection:
                    connection.execute(
                        """
                        INSERT INTO irrigation_schedules(
                            schedule_id, farm_id, device_id, scheduled_for,
                            duration_seconds, enabled, created_at, updated_at, disabled_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        values,
                    )
            except sqlite3.IntegrityError as error:
                raise PersistenceConflict("schedule identity already exists") from error
            except sqlite3.DatabaseError as error:
                raise PersistenceError("SQLite schedule creation failed") from error

    def list_schedules(self) -> tuple[ScheduleSummary, ...]:
        with self._lock:
            connection = self._require_connection()
            try:
                rows = connection.execute(
                    """
                    SELECT s.*,
                           (SELECT o.status FROM irrigation_schedule_occurrences o
                            WHERE o.schedule_id = s.schedule_id
                            ORDER BY o.scheduled_for DESC, o.occurrence_id DESC LIMIT 1)
                           AS occurrence_status
                    FROM irrigation_schedules s
                    ORDER BY s.scheduled_for, s.schedule_id
                    """
                ).fetchall()
            except sqlite3.DatabaseError as error:
                raise PersistenceError("SQLite schedule listing failed") from error
        return tuple(self._row_to_schedule_summary(row) for row in rows)

    def disable_schedule(self, schedule_id: UUID, disabled_at: datetime) -> bool:
        timestamp = format_utc_timestamp(disabled_at, "disabled_at")
        with self._lock:
            connection = self._require_connection()
            try:
                with connection:
                    result = connection.execute(
                        """
                        UPDATE irrigation_schedules
                        SET enabled = 0, disabled_at = COALESCE(disabled_at, ?), updated_at = ?
                        WHERE schedule_id = ?
                        """,
                        (timestamp, timestamp, str(schedule_id)),
                    )
                return result.rowcount == 1
            except sqlite3.DatabaseError as error:
                raise PersistenceError("SQLite schedule disable failed") from error

    def claim_due(self, now: datetime, max_lateness: timedelta) -> tuple[ScheduleOccurrence, ...]:
        timestamp = format_utc_timestamp(now, "now")
        claimed: list[ScheduleOccurrence] = []
        with self._lock:
            connection = self._require_connection()
            try:
                connection.execute("BEGIN IMMEDIATE")
                rows = connection.execute(
                    """
                    SELECT * FROM irrigation_schedules s
                    WHERE enabled = 1 AND scheduled_for <= ?
                      AND NOT EXISTS (
                        SELECT 1 FROM irrigation_schedule_occurrences o
                        WHERE o.schedule_id = s.schedule_id
                          AND o.scheduled_for = s.scheduled_for
                      )
                    ORDER BY scheduled_for, schedule_id
                    """,
                    (timestamp,),
                ).fetchall()
                for row in rows:
                    scheduled_for = parse_utc_timestamp(row["scheduled_for"], "scheduled_for")
                    status = (
                        OccurrenceStatus.MISSED
                        if now - scheduled_for > max_lateness
                        else OccurrenceStatus.CLAIMED
                    )
                    occurrence_id = occurrence_id_for(UUID(row["schedule_id"]), scheduled_for)
                    command_id = command_id_for(occurrence_id)
                    decision_at = timestamp if status is OccurrenceStatus.MISSED else None
                    reason_code = "missed_schedule" if status is OccurrenceStatus.MISSED else None
                    connection.execute(
                        """
                        INSERT INTO irrigation_schedule_occurrences(
                            occurrence_id, schedule_id, farm_id, device_id, scheduled_for,
                            duration_seconds, claimed_at, decision_at, status, reason_code,
                            command_id, ack_status, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
                        """,
                        (
                            str(occurrence_id),
                            row["schedule_id"],
                            row["farm_id"],
                            row["device_id"],
                            row["scheduled_for"],
                            row["duration_seconds"],
                            timestamp,
                            decision_at,
                            status.value,
                            reason_code,
                            str(command_id),
                            timestamp,
                            timestamp,
                        ),
                    )
                    connection.execute(
                        """
                        UPDATE irrigation_schedules
                        SET enabled = 0, disabled_at = ?, updated_at = ?
                        WHERE schedule_id = ? AND enabled = 1
                        """,
                        (timestamp, timestamp, row["schedule_id"]),
                    )
                    claimed.append(
                        ScheduleOccurrence(
                            occurrence_id=occurrence_id,
                            schedule_id=UUID(row["schedule_id"]),
                            farm_id=UUID(row["farm_id"]),
                            device_id=UUID(row["device_id"]),
                            scheduled_for=scheduled_for,
                            duration_seconds=row["duration_seconds"],
                            claimed_at=now,
                            status=status,
                            command_id=command_id,
                            created_at=now,
                            updated_at=now,
                            decision_at=now if decision_at else None,
                            reason_code=reason_code,
                        )
                    )
                connection.commit()
            except sqlite3.IntegrityError as error:
                connection.rollback()
                raise PersistenceError("SQLite schedule claim conflict") from error
            except sqlite3.DatabaseError as error:
                connection.rollback()
                raise PersistenceError("SQLite schedule claim failed") from error
            except (TypeError, ValueError) as error:
                connection.rollback()
                raise PersistenceError("SQLite schedule data is invalid") from error
        return tuple(claimed)

    def mark_occurrence(
        self,
        occurrence_id: UUID,
        status: OccurrenceStatus,
        decided_at: datetime,
        *,
        reason_code: str | None = None,
        ack_status: str | None = None,
    ) -> None:
        if status is OccurrenceStatus.CLAIMED:
            raise ValueError("mark_occurrence requires a terminal scheduler decision")
        timestamp = format_utc_timestamp(decided_at, "decided_at")
        with self._lock:
            connection = self._require_connection()
            try:
                with connection:
                    result = connection.execute(
                        """
                        UPDATE irrigation_schedule_occurrences
                        SET status = ?, decision_at = ?, reason_code = ?, ack_status = ?,
                            updated_at = ?
                        WHERE occurrence_id = ? AND status = 'claimed'
                        """,
                        (
                            status.value,
                            timestamp,
                            reason_code,
                            ack_status,
                            timestamp,
                            str(occurrence_id),
                        ),
                    )
                if result.rowcount != 1:
                    raise PersistenceConflict("occurrence is missing or already terminal")
            except PersistenceConflict:
                raise
            except sqlite3.DatabaseError as error:
                raise PersistenceError("SQLite occurrence update failed") from error

    def recover_non_terminal(self, recovered_at: datetime) -> int:
        timestamp = format_utc_timestamp(recovered_at, "recovered_at")
        with self._lock:
            connection = self._require_connection()
            try:
                with connection:
                    result = connection.execute(
                        """
                        UPDATE irrigation_schedule_occurrences
                        SET status = 'unknown_after_restart', decision_at = ?,
                            reason_code = 'restart_after_claim', updated_at = ?
                        WHERE status = 'claimed'
                        """,
                        (timestamp, timestamp),
                    )
                return result.rowcount
            except sqlite3.DatabaseError as error:
                raise PersistenceError("SQLite schedule recovery failed") from error

    def get_occurrence(self, occurrence_id: UUID) -> ScheduleOccurrence | None:
        with self._lock:
            connection = self._require_connection()
            try:
                row = connection.execute(
                    "SELECT * FROM irrigation_schedule_occurrences WHERE occurrence_id = ?",
                    (str(occurrence_id),),
                ).fetchone()
            except sqlite3.DatabaseError as error:
                raise PersistenceError("SQLite occurrence read failed") from error
        return self._row_to_occurrence(row) if row is not None else None

    def pending(self, *, limit: int) -> tuple[OutboxEntry, ...]:
        if limit < 1:
            raise ValueError("outbox batch limit must be positive")
        with self._lock:
            connection = self._require_connection()
            try:
                rows = connection.execute(
                    """
                    SELECT e.event_id, e.event_type, e.farm_id, e.device_id,
                           e.occurred_at, e.payload AS event_payload,
                           o.topic, o.payload AS publication_payload, o.qos,
                           o.retain, o.attempt_count, o.created_at
                    FROM outbox o JOIN edge_events e USING(event_id)
                    WHERE o.state IN ('pending', 'broker_accepted')
                    ORDER BY e.occurred_at, e.event_id
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            except sqlite3.DatabaseError as error:
                raise PersistenceError("SQLite pending outbox read failed") from error
        return tuple(self._row_to_outbox(row) for row in rows)

    def record_attempt(self, event_id: UUID, attempted_at: datetime) -> None:
        self._update_pending(
            "attempt_count = attempt_count + 1, last_attempt_at = ?",
            format_utc_timestamp(attempted_at, "attempted_at"),
            event_id,
        )

    def mark_broker_accepted(self, event_id: UUID, accepted_at: datetime) -> None:
        timestamp = format_utc_timestamp(accepted_at, "accepted_at")
        with self._lock:
            connection = self._require_connection()
            try:
                event = connection.execute(
                    """
                    SELECT e.event_type, o.state
                    FROM edge_events e JOIN outbox o USING(event_id)
                    WHERE e.event_id = ?
                    """,
                    (str(event_id),),
                ).fetchone()
                if event is None:
                    raise PersistenceError("pending outbox event was not found")
                if event["state"] in {"cloud_confirmed", "rejected", "delivered"}:
                    return
                state = "broker_accepted"
                with connection:
                    updated = connection.execute(
                        """
                        UPDATE outbox SET state = ?, broker_accepted_at = ?
                        WHERE event_id = ? AND state IN ('pending', 'broker_accepted')
                        """,
                        (state, timestamp, str(event_id)),
                    ).rowcount
                if updated != 1:
                    state = connection.execute(
                        "SELECT state FROM outbox WHERE event_id = ?",
                        (str(event_id),),
                    ).fetchone()
                    if state is not None and state["state"] in {
                        "cloud_confirmed",
                        "rejected",
                        "delivered",
                    }:
                        return
                    raise PersistenceError("pending outbox event was not found")
            except PersistenceError:
                raise
            except sqlite3.DatabaseError as error:
                raise PersistenceError("SQLite outbox update failed") from error

    def apply_ingestion_acknowledgement(self, acknowledgement: IngestionAcknowledgement) -> bool:
        target_state = (
            "rejected"
            if acknowledgement.status is IngestionAcknowledgementStatus.REJECTED
            else "cloud_confirmed"
        )
        acknowledged_at = format_utc_timestamp(
            acknowledgement.occurred_at, "acknowledgement.occurred_at"
        )
        with self._lock:
            connection = self._require_connection()
            try:
                row = connection.execute(
                    """
                    SELECT e.event_type, e.farm_id, e.device_id, o.state,
                           o.rejection_reason
                    FROM edge_events e JOIN outbox o USING(event_id)
                    WHERE e.event_id = ?
                    """,
                    (str(acknowledgement.message_id),),
                ).fetchone()
                if row is None:
                    return False
                if (
                    row["event_type"] != acknowledgement.event_type
                    or row["farm_id"] != str(acknowledgement.farm_id)
                    or row["device_id"] != str(acknowledgement.device_id)
                ):
                    raise PersistenceConflict("ingestion acknowledgement identity mismatch")
                if row["state"] in {"cloud_confirmed", "rejected"}:
                    same_terminal = row["state"] == target_state
                    same_reason = (
                        target_state != "rejected"
                        or row["rejection_reason"] == acknowledgement.reason_code
                    )
                    if same_terminal and same_reason:
                        return False
                    raise PersistenceConflict("conflicting terminal ingestion acknowledgement")
                with connection:
                    connection.execute(
                        """
                        UPDATE outbox
                        SET state = ?, cloud_acknowledged_at = ?, rejection_reason = ?
                        WHERE event_id = ?
                        """,
                        (
                            target_state,
                            acknowledged_at,
                            acknowledgement.reason_code,
                            str(acknowledgement.message_id),
                        ),
                    )
                return True
            except PersistenceConflict:
                raise
            except sqlite3.DatabaseError as error:
                raise PersistenceError("SQLite ingestion acknowledgement failed") from error

    def prune(self, cutoff: datetime, now: datetime) -> PruneResult:
        cutoff_value = format_utc_timestamp(cutoff, "cutoff")
        now_value = format_utc_timestamp(now, "now")
        with self._lock:
            connection = self._require_connection()
            try:
                with connection:
                    pending = connection.execute(
                        """
                        SELECT COUNT(*) FROM edge_events e JOIN outbox o USING(event_id)
                        WHERE e.occurred_at <= ?
                          AND o.state IN ('pending', 'broker_accepted')
                        """,
                        (cutoff_value,),
                    ).fetchone()[0]
                    delivered = connection.execute(
                        """
                        SELECT COUNT(*) FROM edge_events e JOIN outbox o USING(event_id)
                        WHERE e.occurred_at <= ?
                          AND o.state IN ('cloud_confirmed', 'rejected', 'delivered')
                        """,
                        (cutoff_value,),
                    ).fetchone()[0]
                    connection.execute(
                        "DELETE FROM edge_events WHERE occurred_at <= ?",
                        (cutoff_value,),
                    )
                    processed = connection.execute(
                        "DELETE FROM processed_commands WHERE expires_at <= ?",
                        (now_value,),
                    ).rowcount
                return PruneResult(pending, delivered, processed)
            except sqlite3.DatabaseError as error:
                raise PersistenceError("SQLite retention cleanup failed") from error

    def get_processed_command(self, command_id: UUID) -> ProcessedCommandRecord | None:
        with self._lock:
            connection = self._require_connection()
            try:
                row = connection.execute(
                    """
                    SELECT command_id, command_fingerprint, acknowledgement_payload,
                           processed_at, expires_at
                    FROM processed_commands WHERE command_id = ?
                    """,
                    (str(command_id),),
                ).fetchone()
            except sqlite3.DatabaseError as error:
                raise PersistenceError("SQLite processed command read failed") from error
        if row is None:
            return None
        return ProcessedCommandRecord(
            command_id=UUID(row["command_id"]),
            command_fingerprint=row["command_fingerprint"],
            acknowledgement=CommandAcknowledgement.from_json(row["acknowledgement_payload"]),
            processed_at=parse_utc_timestamp(row["processed_at"], "processed_at"),
            expires_at=parse_utc_timestamp(row["expires_at"], "expires_at"),
        )

    def save_processed_command(self, record: ProcessedCommandRecord) -> None:
        with self._lock:
            connection = self._require_connection()
            try:
                existing = connection.execute(
                    "SELECT command_fingerprint FROM processed_commands WHERE command_id = ?",
                    (str(record.command_id),),
                ).fetchone()
                if existing is not None and existing[0] != record.command_fingerprint:
                    raise PersistenceConflict(
                        "command identity already exists with different content"
                    )
                with connection:
                    connection.execute(
                        """
                        INSERT INTO processed_commands(
                            command_id, command_fingerprint, acknowledgement_payload,
                            processed_at, expires_at
                        ) VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(command_id) DO UPDATE SET
                            acknowledgement_payload = excluded.acknowledgement_payload,
                            processed_at = excluded.processed_at,
                            expires_at = excluded.expires_at
                        """,
                        (
                            str(record.command_id),
                            record.command_fingerprint,
                            record.acknowledgement.to_json(),
                            format_utc_timestamp(record.processed_at, "processed_at"),
                            format_utc_timestamp(record.expires_at, "expires_at"),
                        ),
                    )
            except PersistenceConflict:
                raise
            except sqlite3.DatabaseError as error:
                raise PersistenceError("SQLite processed command write failed") from error

    def close(self) -> None:
        with self._lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None

    def _update_pending(self, assignment: str, timestamp: str, event_id: UUID) -> None:
        with self._lock:
            connection = self._require_connection()
            try:
                with connection:
                    updated = connection.execute(
                        f"UPDATE outbox SET {assignment} WHERE event_id = ? "
                        "AND state IN ('pending', 'broker_accepted')",
                        (timestamp, str(event_id)),
                    ).rowcount
                if updated != 1:
                    state = connection.execute(
                        "SELECT state FROM outbox WHERE event_id = ?",
                        (str(event_id),),
                    ).fetchone()
                    if state is not None and state["state"] in {
                        "cloud_confirmed",
                        "rejected",
                        "delivered",
                    }:
                        return
                    raise PersistenceError("pending outbox event was not found")
            except PersistenceError:
                raise
            except sqlite3.DatabaseError as error:
                raise PersistenceError("SQLite outbox update failed") from error

    def _require_connection(self) -> sqlite3.Connection:
        if self._connection is None:
            raise PersistenceError("SQLite store is not initialized")
        return self._connection

    @staticmethod
    def _row_to_outbox(row: sqlite3.Row) -> OutboxEntry:
        event = EdgeEvent(
            event_id=UUID(row["event_id"]),
            event_type=EdgeEventType(row["event_type"]),
            farm_id=UUID(row["farm_id"]),
            device_id=UUID(row["device_id"]),
            occurred_at=parse_utc_timestamp(row["occurred_at"], "occurred_at"),
            payload=row["event_payload"],
        )
        return OutboxEntry(
            event=event,
            publication=MqttPublication(
                topic=row["topic"],
                payload=row["publication_payload"],
                qos=row["qos"],
                retain=bool(row["retain"]),
            ),
            attempt_count=row["attempt_count"],
            created_at=parse_utc_timestamp(row["created_at"], "created_at"),
        )

    @staticmethod
    def _row_to_schedule_summary(row: sqlite3.Row) -> ScheduleSummary:
        schedule = IrrigationSchedule(
            schedule_id=UUID(row["schedule_id"]),
            farm_id=UUID(row["farm_id"]),
            device_id=UUID(row["device_id"]),
            scheduled_for=parse_utc_timestamp(row["scheduled_for"], "scheduled_for"),
            duration_seconds=row["duration_seconds"],
            enabled=bool(row["enabled"]),
            created_at=parse_utc_timestamp(row["created_at"], "created_at"),
            updated_at=parse_utc_timestamp(row["updated_at"], "updated_at"),
            disabled_at=(
                parse_utc_timestamp(row["disabled_at"], "disabled_at")
                if row["disabled_at"] is not None
                else None
            ),
        )
        raw_status = row["occurrence_status"]
        return ScheduleSummary(
            schedule,
            OccurrenceStatus(raw_status) if raw_status is not None else None,
        )

    @staticmethod
    def _row_to_occurrence(row: sqlite3.Row) -> ScheduleOccurrence:
        return ScheduleOccurrence(
            occurrence_id=UUID(row["occurrence_id"]),
            schedule_id=UUID(row["schedule_id"]),
            farm_id=UUID(row["farm_id"]),
            device_id=UUID(row["device_id"]),
            scheduled_for=parse_utc_timestamp(row["scheduled_for"], "scheduled_for"),
            duration_seconds=row["duration_seconds"],
            claimed_at=parse_utc_timestamp(row["claimed_at"], "claimed_at"),
            decision_at=(
                parse_utc_timestamp(row["decision_at"], "decision_at")
                if row["decision_at"] is not None
                else None
            ),
            status=OccurrenceStatus(row["status"]),
            reason_code=row["reason_code"],
            command_id=UUID(row["command_id"]),
            ack_status=row["ack_status"],
            created_at=parse_utc_timestamp(row["created_at"], "created_at"),
            updated_at=parse_utc_timestamp(row["updated_at"], "updated_at"),
        )
