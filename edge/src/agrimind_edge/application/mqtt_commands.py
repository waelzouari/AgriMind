"""Broker-neutral MQTT pump-command processing and acknowledgement publication."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from agrimind_edge.application.mqtt_ports import MqttTransport
from agrimind_edge.application.persistence_ports import DurableEventPublisher
from agrimind_edge.application.pump_command_handler import PumpCommandHandler
from agrimind_edge.contracts import CommandAcknowledgement, PumpCommand
from agrimind_edge.contracts.enums import AcknowledgementStatus
from agrimind_edge.contracts.topics import TopicBuilder
from agrimind_edge.contracts.validation import decode_json, parse_uuid
from agrimind_edge.domain.mqtt import MqttPublication, ReceivedMqttMessage
from agrimind_edge.domain.persistence import EdgeEvent
from agrimind_edge.domain.pump import PumpDecisionCode

MQTT_QOS_AT_LEAST_ONCE = 1
# The largest canonical v1 payload is currently a maximal device status at 1,471 bytes.
# Commands are smaller; 4 KiB preserves generous protocol headroom while bounding decoding.
MAX_INBOUND_MQTT_PAYLOAD_BYTES = 4_096


class MqttAcknowledgementPublisher:
    """Publish v1 acknowledgements without exposing transport details to pump logic."""

    def __init__(
        self,
        transport: MqttTransport,
        topics: TopicBuilder,
        *,
        durable_publisher: DurableEventPublisher | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._transport = transport
        self._topics = topics
        self._durable_publisher = durable_publisher
        self._logger = logger or logging.getLogger(__name__)

    def publish(self, acknowledgement: CommandAcknowledgement) -> None:
        publication = MqttPublication(
            topic=self._topics.acknowledgement(acknowledgement.command_id),
            payload=acknowledgement.to_json(),
            qos=MQTT_QOS_AT_LEAST_ONCE,
            retain=False,
        )
        try:
            if self._durable_publisher is None:
                self._transport.publish(publication)
            else:
                self._durable_publisher.submit(
                    EdgeEvent.from_acknowledgement(acknowledgement),
                    publication,
                    attempt_now=True,
                    replay_delivered=True,
                )
        except Exception:
            self._logger.warning(
                "mqtt_ack_publish_failed",
                extra={
                    "event": "mqtt_ack_publish_failed",
                    "command_id": str(acknowledgement.command_id),
                    "status": acknowledgement.status.value,
                },
            )
            return


class MqttPumpCommandProcessor:
    """Validate inbound MQTT envelopes and delegate commands to AGM-005."""

    def __init__(
        self,
        handler: PumpCommandHandler,
        acknowledgement_publisher: MqttAcknowledgementPublisher,
        topics: TopicBuilder,
        *,
        clock: Callable[[], datetime] | None = None,
        acknowledgement_id_factory: Callable[[], UUID] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._handler = handler
        self._acknowledgement_publisher = acknowledgement_publisher
        self._topics = topics
        self._clock = clock or (lambda: datetime.now(UTC))
        self._acknowledgement_id_factory = acknowledgement_id_factory or uuid4
        self._logger = logger or logging.getLogger(__name__)

    def process(self, message: ReceivedMqttMessage) -> None:
        if message.topic != self._topics.pump_command():
            self._log_rejection("unexpected_topic", None)
            return
        if message.retain:
            self._log_rejection("retained_command", None)
            return
        if len(message.payload) > MAX_INBOUND_MQTT_PAYLOAD_BYTES:
            self._log_rejection("payload_too_large", None)
            return

        command_id = self._extract_command_id(message.payload)
        if command_id is None:
            self._log_rejection("uncorrelatable_command", None)
            return

        try:
            command = PumpCommand.from_json_without_expiry_validation(message.payload)
        except ValueError:
            acknowledgement = CommandAcknowledgement(
                acknowledgement_id=self._acknowledgement_id_factory(),
                command_id=command_id,
                farm_id=self._topics.farm_id,
                device_id=self._topics.device_id,
                status=AcknowledgementStatus.REJECTED,
                occurred_at=self._now(),
                reason_code=PumpDecisionCode.INVALID_COMMAND.value,
            )
            self._log_rejection(PumpDecisionCode.INVALID_COMMAND.value, command_id)
            self._acknowledgement_publisher.publish(acknowledgement)
            return

        try:
            acknowledgement = self._handler.handle(command)
        except Exception:
            self._logger.error(
                "mqtt_pump_command_processing_failed",
                extra={
                    "event": "mqtt_pump_command_processing_failed",
                    "command_id": str(command.command_id),
                },
            )
            return
        self._acknowledgement_publisher.publish(acknowledgement)

    def _extract_command_id(self, payload: bytes) -> UUID | None:
        try:
            data = decode_json(payload)
            return parse_uuid(data.get("command_id"), "command_id")
        except (RecursionError, ValueError):
            return None

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() != UTC.utcoffset(now):
            raise ValueError("MQTT command processor clock must return UTC")
        return now

    def _log_rejection(self, reason: str, command_id: UUID | None) -> None:
        self._logger.warning(
            "mqtt_pump_command_rejected",
            extra={
                "event": "mqtt_pump_command_rejected",
                "command_id": str(command_id) if command_id is not None else None,
                "reason_code": reason,
            },
        )
