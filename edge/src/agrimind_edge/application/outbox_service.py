"""Durable at-least-once MQTT publication orchestration."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from threading import Lock, Thread

from agrimind_edge.application.mqtt_ports import MqttTransport
from agrimind_edge.application.persistence_ports import (
    EventOutboxStore,
    PersistenceConflict,
    PersistenceError,
)
from agrimind_edge.domain.mqtt import MqttPublication
from agrimind_edge.domain.persistence import EdgeEvent, EnqueueResult, OutboxEntry

DrainSubmitter = Callable[[Callable[[], None]], None]


def _thread_submitter(callback: Callable[[], None]) -> None:
    Thread(target=callback, name="agrimind-outbox", daemon=True).start()


class OutboxService:
    def __init__(
        self,
        store: EventOutboxStore,
        transport: MqttTransport,
        *,
        clock: Callable[[], datetime] | None = None,
        retention: timedelta = timedelta(hours=24),
        batch_size: int = 100,
        confirmation_timeout_seconds: float = 10.0,
        drain_submitter: DrainSubmitter = _thread_submitter,
        logger: logging.Logger | None = None,
    ) -> None:
        if retention != timedelta(hours=24):
            raise ValueError("AGM-008 retention must be exactly 24 hours")
        if batch_size < 1:
            raise ValueError("outbox batch size must be positive")
        if confirmation_timeout_seconds <= 0:
            raise ValueError("MQTT confirmation timeout must be positive")
        self._store = store
        self._transport = transport
        self._clock = clock or (lambda: datetime.now(UTC))
        self._retention = retention
        self._batch_size = batch_size
        self._confirmation_timeout_seconds = confirmation_timeout_seconds
        self._drain_submitter = drain_submitter
        self._logger = logger or logging.getLogger(__name__)
        self._available = False
        self._drain_lock = Lock()

    def initialize(self) -> bool:
        try:
            self._store.initialize()
            self._available = True
            self._prune()
        except PersistenceError:
            self._available = False
            self._logger.error(
                "edge_persistence_unavailable",
                extra={"event": "edge_persistence_unavailable", "operation": "initialize"},
            )
        return self._available

    def submit(
        self,
        event: EdgeEvent,
        publication: MqttPublication,
        *,
        attempt_now: bool,
        replay_delivered: bool = False,
    ) -> bool:
        if not self._available and not self.initialize():
            return self._direct_fallback(event, publication, attempt_now)
        try:
            result = self._store.enqueue(event, publication, self._now())
            self._prune()
        except PersistenceConflict:
            self._logger.error(
                "edge_event_identity_conflict",
                extra={
                    "event": "edge_event_identity_conflict",
                    "event_id": str(event.event_id),
                    "event_type": event.event_type.value,
                },
            )
            return False
        except PersistenceError:
            self._available = False
            self._logger.error(
                "edge_event_not_durable",
                extra={
                    "event": "edge_event_not_durable",
                    "event_id": str(event.event_id),
                    "event_type": event.event_type.value,
                },
            )
            return self._direct_fallback(event, publication, attempt_now)

        if result is EnqueueResult.DELIVERED:
            if replay_delivered and attempt_now:
                return self._publish_direct(publication)
            return True
        if not attempt_now:
            return False
        try:
            return self._attempt(OutboxEntry(event, publication, 0, self._now()))
        except PersistenceError:
            self._available = False
            self._logger.error(
                "edge_persistence_unavailable",
                extra={"event": "edge_persistence_unavailable", "operation": "publish"},
            )
            return False

    def request_drain(self) -> None:
        self._drain_submitter(self.drain)

    def drain(self) -> None:
        if not self._drain_lock.acquire(blocking=False):
            return
        continue_draining = False
        try:
            if not self._available and not self.initialize():
                return
            self._prune()
            entries = self._store.pending(limit=self._batch_size)
            for entry in entries:
                if not self._attempt(entry):
                    break
            else:
                continue_draining = len(entries) == self._batch_size
        except PersistenceError:
            self._available = False
            self._logger.error(
                "edge_persistence_unavailable",
                extra={"event": "edge_persistence_unavailable", "operation": "drain"},
            )
        finally:
            self._drain_lock.release()
        if continue_draining:
            self.request_drain()

    def close(self) -> None:
        self._store.close()
        self._available = False

    def _attempt(self, entry: OutboxEntry) -> bool:
        try:
            self._store.record_attempt(entry.event.event_id, self._now())
            receipt = self._transport.publish(entry.publication)
            if not receipt.wait_for_confirmation(self._confirmation_timeout_seconds):
                self._logger.warning(
                    "mqtt_outbox_confirmation_pending",
                    extra={
                        "event": "mqtt_outbox_confirmation_pending",
                        "event_id": str(entry.event.event_id),
                    },
                )
                return False
            self._store.mark_delivered(entry.event.event_id, self._now())
            return True
        except PersistenceError:
            raise
        except Exception:
            self._logger.warning(
                "mqtt_outbox_publish_failed",
                extra={
                    "event": "mqtt_outbox_publish_failed",
                    "event_id": str(entry.event.event_id),
                },
            )
            return False

    def _direct_fallback(
        self,
        event: EdgeEvent,
        publication: MqttPublication,
        attempt_now: bool,
    ) -> bool:
        if attempt_now and self._publish_direct(publication):
            self._logger.warning(
                "edge_event_published_without_durability",
                extra={
                    "event": "edge_event_published_without_durability",
                    "event_id": str(event.event_id),
                    "event_type": event.event_type.value,
                },
            )
            return True
        self._logger.error(
            "edge_event_lost",
            extra={
                "event": "edge_event_lost",
                "event_id": str(event.event_id),
                "event_type": event.event_type.value,
            },
        )
        return False

    def _publish_direct(self, publication: MqttPublication) -> bool:
        try:
            receipt = self._transport.publish(publication)
            return receipt.wait_for_confirmation(self._confirmation_timeout_seconds)
        except Exception:
            return False

    def _prune(self) -> None:
        now = self._now()
        result = self._store.prune(now - self._retention, now)
        if result.pending_events or result.delivered_events or result.processed_commands:
            self._logger.warning(
                "edge_retention_pruned",
                extra={
                    "event": "edge_retention_pruned",
                    "pending_events": result.pending_events,
                    "delivered_events": result.delivered_events,
                    "processed_commands": result.processed_commands,
                },
            )

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() != UTC.utcoffset(now):
            raise ValueError("outbox clock must return UTC")
        return now
