"""Cloud MQTT connection lifecycle, presence, and telemetry publication."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from threading import RLock
from uuid import UUID, uuid4

from agrimind_edge.application.mqtt_ports import (
    DeviceStatusSource,
    MessageHandler,
    MqttTransport,
)
from agrimind_edge.application.persistence_ports import DurableEventPublisher
from agrimind_edge.application.telemetry import TelemetryMapper
from agrimind_edge.contracts.enums import DeviceHealth
from agrimind_edge.contracts.models import DeviceStatus
from agrimind_edge.contracts.topics import TopicBuilder
from agrimind_edge.domain.mqtt import (
    MqttConnectionState,
    MqttPublication,
    TelemetryPublishResult,
)
from agrimind_edge.domain.persistence import EdgeEvent
from agrimind_edge.domain.sensors import SensorSnapshot

MQTT_QOS_AT_LEAST_ONCE = 1


class CloudMqttService:
    """Coordinate MQTT without exposing broker objects to sensors or pump logic."""

    def __init__(
        self,
        transport: MqttTransport,
        mapper: TelemetryMapper,
        topics: TopicBuilder,
        status_source: DeviceStatusSource,
        *,
        command_message_handler: MessageHandler | None = None,
        ingestion_acknowledgement_handler: MessageHandler | None = None,
        durable_publisher: DurableEventPublisher | None = None,
        clock: Callable[[], datetime] | None = None,
        message_id_factory: Callable[[], UUID] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._transport = transport
        self._mapper = mapper
        self._topics = topics
        self._status_source = status_source
        self._command_message_handler = command_message_handler
        self._ingestion_acknowledgement_handler = ingestion_acknowledgement_handler
        self._durable_publisher = durable_publisher
        self._clock = clock or (lambda: datetime.now(UTC))
        self._message_id_factory = message_id_factory or uuid4
        self._logger = logger or logging.getLogger(__name__)
        self._state = MqttConnectionState.DISCONNECTED
        self._lock = RLock()
        transport.set_connection_handlers(self._on_connected, self._on_disconnected)

    @property
    def state(self) -> MqttConnectionState:
        with self._lock:
            return self._state

    def start(self) -> None:
        with self._lock:
            if self._state in {MqttConnectionState.CONNECTING, MqttConnectionState.CONNECTED}:
                return
            if self._durable_publisher is not None:
                self._durable_publisher.initialize()
            self._transport.configure_last_will(
                self._status_publication(online=False, session_lost=True)
            )
            self._state = MqttConnectionState.CONNECTING
            try:
                self._transport.connect()
            except Exception:
                self._state = MqttConnectionState.DISCONNECTED
                self._logger.warning(
                    "mqtt_connect_deferred",
                    extra={"event": "mqtt_connect_deferred", "state": self._state.value},
                )

    def stop(self) -> None:
        with self._lock:
            if self._state is MqttConnectionState.CONNECTED:
                try:
                    self._transport.publish(
                        self._status_publication(online=False, session_lost=False)
                    )
                except Exception:
                    self._logger.warning(
                        "mqtt_offline_status_failed",
                        extra={"event": "mqtt_offline_status_failed"},
                    )
            try:
                self._transport.disconnect()
            finally:
                self._state = MqttConnectionState.STOPPED

    def publish_snapshot(self, snapshot: SensorSnapshot) -> TelemetryPublishResult:
        mapping = self._mapper.map_snapshot(snapshot)
        with self._lock:
            connected = self._state is MqttConnectionState.CONNECTED
            if not connected and self._durable_publisher is None:
                self._logger.info(
                    "telemetry_skipped_offline",
                    extra={
                        "event": "telemetry_skipped_offline",
                        "correlation_id": snapshot.correlation_id,
                        "mapped": len(mapping.telemetry),
                    },
                )
                return TelemetryPublishResult(
                    mapped=len(mapping.telemetry),
                    published=0,
                    skipped_unavailable=mapping.skipped_unavailable,
                    connection_state=self._state,
                )

            published = 0
            for telemetry in mapping.telemetry:
                publication = MqttPublication(
                    topic=self._topics.telemetry(telemetry.metric),
                    payload=telemetry.to_json(),
                    qos=MQTT_QOS_AT_LEAST_ONCE,
                    retain=False,
                )
                try:
                    if self._durable_publisher is None:
                        self._transport.publish(publication)
                        was_published = True
                    else:
                        was_published = self._durable_publisher.submit(
                            EdgeEvent.from_telemetry(telemetry),
                            publication,
                            attempt_now=connected,
                        )
                except Exception:
                    self._logger.warning(
                        "telemetry_publish_failed",
                        extra={
                            "event": "telemetry_publish_failed",
                            "correlation_id": snapshot.correlation_id,
                            "metric": telemetry.metric.value,
                        },
                    )
                    continue
                published += int(was_published)
            return TelemetryPublishResult(
                mapped=len(mapping.telemetry),
                published=published,
                skipped_unavailable=mapping.skipped_unavailable,
                connection_state=self._state,
            )

    def _on_connected(self) -> None:
        with self._lock:
            self._state = MqttConnectionState.CONNECTED
            try:
                self._transport.publish(self._status_publication(online=True, session_lost=False))
            except Exception:
                self._logger.warning(
                    "mqtt_online_status_failed",
                    extra={"event": "mqtt_online_status_failed"},
                )
            if self._command_message_handler is not None:
                try:
                    self._transport.subscribe(
                        self._topics.pump_command(),
                        MQTT_QOS_AT_LEAST_ONCE,
                        self._command_message_handler,
                    )
                except Exception:
                    self._logger.warning(
                        "mqtt_command_subscription_failed",
                        extra={
                            "event": "mqtt_command_subscription_failed",
                            "topic": self._topics.pump_command(),
                        },
                    )
            if self._ingestion_acknowledgement_handler is not None:
                try:
                    self._transport.subscribe(
                        self._topics.ingestion_acknowledgement_filter(),
                        MQTT_QOS_AT_LEAST_ONCE,
                        self._ingestion_acknowledgement_handler,
                    )
                except Exception:
                    self._logger.warning(
                        "mqtt_ingestion_ack_subscription_failed",
                        extra={"event": "mqtt_ingestion_ack_subscription_failed"},
                    )
            if self._durable_publisher is not None:
                self._durable_publisher.request_drain()
            self._logger.info(
                "mqtt_connected",
                extra={"event": "mqtt_connected", "state": self._state.value},
            )

    def _on_disconnected(self) -> None:
        with self._lock:
            if self._state is not MqttConnectionState.STOPPED:
                self._state = MqttConnectionState.DISCONNECTED
            self._logger.warning(
                "mqtt_disconnected",
                extra={"event": "mqtt_disconnected", "state": self._state.value},
            )

    def _status_publication(self, *, online: bool, session_lost: bool) -> MqttPublication:
        status = self._status_source.read_status()
        errors = status.errors
        health = status.health
        if session_lost:
            errors = (*errors, "mqtt_session_lost")
            if health is DeviceHealth.HEALTHY:
                health = DeviceHealth.DEGRADED
        payload = DeviceStatus(
            message_id=self._message_id_factory(),
            farm_id=self._topics.farm_id,
            device_id=self._topics.device_id,
            online=online,
            pump_state=status.pump_state,
            health=health,
            recorded_at=self._now(),
            uptime_seconds=status.uptime_seconds,
            firmware_version=status.firmware_version,
            errors=errors,
        )
        return MqttPublication(
            topic=self._topics.device_status(),
            payload=payload.to_json(),
            qos=MQTT_QOS_AT_LEAST_ONCE,
            retain=True,
        )

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() != UTC.utcoffset(now):
            raise ValueError("MQTT service clock must return UTC")
        return now
