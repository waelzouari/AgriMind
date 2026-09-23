"""Narrow application ports for durable edge events and command receipts."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from agrimind_edge.contracts import IngestionAcknowledgement
from agrimind_edge.domain.mqtt import MqttPublication
from agrimind_edge.domain.persistence import (
    EdgeEvent,
    EnqueueResult,
    OutboxEntry,
    ProcessedCommandRecord,
    PruneResult,
)


class PersistenceError(RuntimeError):
    """Base exception for unavailable or invalid persistence operations."""


class PersistenceConflict(PersistenceError):
    """An existing identity was reused with different immutable content."""


class EventOutboxStore(Protocol):
    def initialize(self) -> None: ...

    def enqueue(
        self,
        event: EdgeEvent,
        publication: MqttPublication,
        created_at: datetime,
    ) -> EnqueueResult: ...

    def pending(self, *, limit: int) -> tuple[OutboxEntry, ...]: ...

    def record_attempt(self, event_id: UUID, attempted_at: datetime) -> None: ...

    def mark_broker_accepted(self, event_id: UUID, accepted_at: datetime) -> None: ...

    def apply_ingestion_acknowledgement(
        self, acknowledgement: IngestionAcknowledgement
    ) -> bool: ...

    def prune(self, cutoff: datetime, now: datetime) -> PruneResult: ...

    def close(self) -> None: ...


class ProcessedCommandStore(Protocol):
    def get_processed_command(self, command_id: UUID) -> ProcessedCommandRecord | None: ...

    def save_processed_command(self, record: ProcessedCommandRecord) -> None: ...


class DurableEventPublisher(Protocol):
    def initialize(self) -> bool: ...

    def submit(
        self,
        event: EdgeEvent,
        publication: MqttPublication,
        *,
        attempt_now: bool,
        replay_delivered: bool = False,
    ) -> bool: ...

    def request_drain(self) -> None: ...
