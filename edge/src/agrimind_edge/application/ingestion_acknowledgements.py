"""Validate Cloud ingestion receipts before mutating the local outbox."""

from __future__ import annotations

import logging
from uuid import UUID

from agrimind_edge.application.persistence_ports import (
    EventOutboxStore,
    PersistenceConflict,
    PersistenceError,
)
from agrimind_edge.contracts import IngestionAcknowledgement, TopicBuilder
from agrimind_edge.domain.mqtt import ReceivedMqttMessage


class IngestionAcknowledgementProcessor:
    def __init__(
        self,
        store: EventOutboxStore,
        topics: TopicBuilder,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self._store = store
        self._topics = topics
        self._logger = logger or logging.getLogger(__name__)

    def process(self, message: ReceivedMqttMessage) -> None:
        try:
            prefix = f"{self._topics.base}/sync/acks/"
            if not message.topic.startswith(prefix):
                raise ValueError("unexpected acknowledgement topic")
            suffix = message.topic.removeprefix(prefix)
            message_id = UUID(suffix)
            if message_id.int == 0 or str(message_id) != suffix:
                raise ValueError("noncanonical acknowledgement topic identity")
            acknowledgement = IngestionAcknowledgement.from_json(message.payload)
            if acknowledgement.message_id != message_id:
                raise ValueError("topic and payload message identity differ")
            if (
                acknowledgement.farm_id != self._topics.farm_id
                or acknowledgement.device_id != self._topics.device_id
            ):
                raise ValueError("acknowledgement target differs from local identity")
            changed = self._store.apply_ingestion_acknowledgement(acknowledgement)
            self._logger.info(
                "ingestion_acknowledgement_applied",
                extra={
                    "event": "ingestion_acknowledgement_applied",
                    "message_id": str(message_id),
                    "status": acknowledgement.status.value,
                    "changed": changed,
                },
            )
        except (ValueError, PersistenceConflict, PersistenceError):
            self._logger.warning(
                "ingestion_acknowledgement_rejected",
                extra={"event": "ingestion_acknowledgement_rejected"},
            )
