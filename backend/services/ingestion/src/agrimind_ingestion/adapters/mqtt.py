"""Persistent verified-TLS MQTT consumer for the trusted ingestion service."""

from __future__ import annotations

import logging
import ssl
from collections.abc import Callable
from pathlib import Path
from threading import RLock
from typing import Any, Protocol

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

from agrimind_ingestion.application.acknowledgements import (
    IngestionAcknowledgementFactory,
)
from agrimind_ingestion.domain import IngestionResult

TELEMETRY_FILTER = "agrimind/v1/farms/+/devices/+/telemetry/+"
STATUS_FILTER = "agrimind/v1/farms/+/devices/+/status/device"


class MessageProcessor(Protocol):
    def process(self, topic: str, payload: bytes, *, qos: int, retain: bool) -> IngestionResult: ...


class PahoIngestionConsumer:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        client_id: str,
        username: str,
        password: str,
        ca_file: Path,
        processor: MessageProcessor,
        client: Any | None = None,
        ssl_context_factory: Callable[..., ssl.SSLContext] = ssl.create_default_context,
        logger: logging.Logger | None = None,
        acknowledgement_factory: IngestionAcknowledgementFactory | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._processor = processor
        self._logger = logger or logging.getLogger(__name__)
        self._acknowledgements = acknowledgement_factory or IngestionAcknowledgementFactory()
        self._pending_application_acknowledgements: dict[int, tuple[int, int]] = {}
        self._ack_lock = RLock()
        self._client = client or mqtt.Client(
            CallbackAPIVersion.VERSION2,
            client_id=client_id,
            clean_session=False,
            protocol=mqtt.MQTTv311,
            reconnect_on_failure=True,
        )
        self._client.username_pw_set(username, password)
        context = ssl_context_factory(cafile=str(ca_file))
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        self._client.tls_set_context(context)
        self._client.manual_ack_set(True)
        self._client.reconnect_delay_set(min_delay=1, max_delay=60)
        self._client.on_connect = self._on_connect
        self._client.on_connect_fail = self._on_connect_fail
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message
        self._client.on_publish = self._on_publish

    def start(self) -> None:
        self._client.connect_async(self._host, self._port, keepalive=60)
        result = self._client.loop_start()
        if result != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError("MQTT ingestion loop failed to start")

    def stop(self) -> None:
        self._client.disconnect()
        self._client.loop_stop()

    def _on_connect(
        self,
        client: Any,
        userdata: Any,
        flags: Any,
        reason_code: Any,
        properties: Any,
    ) -> None:
        del userdata, flags, properties
        if getattr(reason_code, "is_failure", True):
            self._logger.warning(
                "ingestion_mqtt_connection_rejected",
                extra={"event": "ingestion_mqtt_connection_rejected"},
            )
            return
        for topic_filter in (TELEMETRY_FILTER, STATUS_FILTER):
            result, _message_id = client.subscribe(topic_filter, qos=1)
            if result != mqtt.MQTT_ERR_SUCCESS:
                raise RuntimeError("MQTT ingestion subscription was rejected")
        self._logger.info(
            "ingestion_mqtt_connected",
            extra={"event": "ingestion_mqtt_connected"},
        )

    def _on_connect_fail(self, client: Any, userdata: Any) -> None:
        del client, userdata
        self._logger.warning(
            "ingestion_mqtt_connect_failed",
            extra={"event": "ingestion_mqtt_connect_failed"},
        )

    def _on_disconnect(
        self,
        client: Any,
        userdata: Any,
        disconnect_flags: Any,
        reason_code: Any,
        properties: Any,
    ) -> None:
        del client, userdata, disconnect_flags, reason_code, properties
        with self._ack_lock:
            self._pending_application_acknowledgements.clear()
        self._logger.warning(
            "ingestion_mqtt_disconnected",
            extra={"event": "ingestion_mqtt_disconnected"},
        )

    def _on_message(self, client: Any, userdata: Any, message: Any) -> None:
        del userdata
        try:
            result = self._processor.process(
                message.topic,
                bytes(message.payload),
                qos=message.qos,
                retain=message.retain,
            )
        except Exception:
            self._logger.error(
                "ingestion_unexpected_failure",
                extra={"event": "ingestion_unexpected_failure"},
            )
            client.disconnect()
            return
        if result.terminal:
            publication = self._acknowledgements.create(result)
            if publication is not None:
                with self._ack_lock:
                    published = client.publish(
                        publication.topic,
                        publication.payload,
                        qos=publication.qos,
                        retain=publication.retain,
                    )
                    if published.rc != mqtt.MQTT_ERR_SUCCESS:
                        self._logger.warning(
                            "ingestion_application_ack_publish_failed",
                            extra={"event": "ingestion_application_ack_publish_failed"},
                        )
                        client.disconnect()
                        return
                    self._pending_application_acknowledgements[published.mid] = (
                        message.mid,
                        message.qos,
                    )
                return
            acknowledgement_result = client.ack(message.mid, message.qos)
            if acknowledgement_result != mqtt.MQTT_ERR_SUCCESS:
                self._logger.warning(
                    "ingestion_mqtt_ack_failed",
                    extra={"event": "ingestion_mqtt_ack_failed"},
                )
            return
        self._logger.warning(
            "ingestion_retry_deferred",
            extra={"event": "ingestion_retry_deferred"},
        )
        client.disconnect()

    def _on_publish(
        self,
        client: Any,
        userdata: Any,
        message_id: int,
        reason_code: Any,
        properties: Any,
    ) -> None:
        del userdata, reason_code, properties
        with self._ack_lock:
            inbound = self._pending_application_acknowledgements.pop(message_id, None)
        if inbound is None:
            return
        if client.ack(*inbound) != mqtt.MQTT_ERR_SUCCESS:
            self._logger.warning(
                "ingestion_mqtt_ack_failed",
                extra={"event": "ingestion_mqtt_ack_failed"},
            )
