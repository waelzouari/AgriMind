"""Publish only observable irrigation feedback through the durable outbox."""

from __future__ import annotations

import logging

from agrimind_edge.application.mqtt_ports import MqttTransport
from agrimind_edge.application.persistence_ports import DurableEventPublisher
from agrimind_edge.contracts import IrrigationResult, TopicBuilder
from agrimind_edge.domain.mqtt import MqttPublication
from agrimind_edge.domain.persistence import EdgeEvent

MQTT_QOS_AT_LEAST_ONCE = 1


class IrrigationResultPublisher:
    """Publish a prevalidated, measured V1 result without creating one."""

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

    def publish(self, result: IrrigationResult) -> bool:
        if result.farm_id != self._topics.farm_id or result.device_id != self._topics.device_id:
            raise ValueError("irrigation result target differs from local identity")
        publication = MqttPublication(
            topic=self._topics.irrigation_result(),
            payload=result.to_json(),
            qos=MQTT_QOS_AT_LEAST_ONCE,
            retain=False,
        )
        try:
            if self._durable_publisher is None:
                self._transport.publish(publication)
                return True
            return self._durable_publisher.submit(
                EdgeEvent.from_irrigation_result(result),
                publication,
                attempt_now=True,
            )
        except Exception:
            self._logger.warning(
                "irrigation_result_publish_failed",
                extra={
                    "event": "irrigation_result_publish_failed",
                    "event_id": str(result.event_id),
                },
            )
            return False
