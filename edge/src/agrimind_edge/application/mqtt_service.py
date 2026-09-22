"""Cloud MQTT connection lifecycle, presence, and telemetry publication."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from threading import RLock
from uuid import UUID, uuid4

from agrimind_edge.application.mqtt_ports import DeviceStatusSource, MqttTransport
from agrimind_edge.application.telemetry import TelemetryMapper
from agrimind_edge.contracts.enums import DeviceHealth
from agrimind_edge.contracts.models import DeviceStatus
from agrimind_edge.contracts.topics import TopicBuilder
from agrimind_edge.domain.mqtt import (
    MqttConnectionState,
    MqttPublication,
    TelemetryPublishResult,
)
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
        clock: Callable[[], datetime] | None = None,
        message_id_factory: Callable[[], UUID] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._transport = transport
        self._mapper = mapper
        self._topics = topics
        self._status_source = status_source
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
            if self._state is not MqttConnectionState.CONNECTED:
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
                    self._transport.publish(publication)
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
                published += 1
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
