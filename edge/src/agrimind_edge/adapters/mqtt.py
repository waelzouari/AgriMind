"""Eclipse Paho MQTT adapter with verified TLS and bounded reconnect backoff."""

from __future__ import annotations

import logging
import ssl
from collections.abc import Callable
from typing import Any

import paho.mqtt.client as mqtt

from agrimind_edge.application.mqtt_ports import (
    ConnectionHandler,
    DisconnectionHandler,
    MessageHandler,
    MqttPublishReceipt,
)
from agrimind_edge.config.runtime import MqttConfig, MqttCredentials
from agrimind_edge.domain.mqtt import MqttPublication, ReceivedMqttMessage


class PahoMqttTransport:
    """Keep all Paho-specific types inside the infrastructure adapter."""

    def __init__(
        self,
        config: MqttConfig,
        credentials: MqttCredentials,
        *,
        client: Any | None = None,
        ssl_context_factory: Callable[..., ssl.SSLContext] = ssl.create_default_context,
        require_verified_tls: bool = True,
        logger: logging.Logger | None = None,
    ) -> None:
        if require_verified_tls and (not config.tls_enabled or config.ca_file is None):
            raise ValueError("cloud MQTT transport requires verified TLS and a CA file")
        self._config = config
        self._logger = logger or logging.getLogger(__name__)
        self._client = client or mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"agrimind-{config.device_id}",
            protocol=mqtt.MQTTv311,
            reconnect_on_failure=True,
        )
        self._on_connected: ConnectionHandler = lambda: None
        self._on_disconnected: DisconnectionHandler = lambda: None
        self._will_configured = False
        self._message_handlers: dict[str, MessageHandler] = {}

        self._client.username_pw_set(credentials.username, credentials.password)
        if config.tls_enabled:
            if config.ca_file is None:
                raise ValueError("a CA file is required when MQTT TLS is enabled")
            context = ssl_context_factory(cafile=str(config.ca_file))
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.check_hostname = True
            context.verify_mode = ssl.CERT_REQUIRED
            self._client.tls_set_context(context)
        self._client.reconnect_delay_set(
            min_delay=config.reconnect_min_seconds,
            max_delay=config.reconnect_max_seconds,
        )
        self._client.on_connect = self._handle_connect
        self._client.on_connect_fail = self._handle_connect_fail
        self._client.on_disconnect = self._handle_disconnect
        self._client.on_message = self._handle_message

    def set_connection_handlers(
        self,
        on_connected: ConnectionHandler,
        on_disconnected: DisconnectionHandler,
    ) -> None:
        self._on_connected = on_connected
        self._on_disconnected = on_disconnected

    def configure_last_will(self, publication: MqttPublication) -> None:
        self._client.will_set(
            publication.topic,
            publication.payload,
            qos=publication.qos,
            retain=publication.retain,
        )
        self._will_configured = True

    def connect(self) -> None:
        if not self._will_configured:
            raise RuntimeError("MQTT last will must be configured before connect")
        self._client.connect_async(
            self._config.host,
            self._config.port,
            keepalive=self._config.keepalive_seconds,
        )
        result = self._client.loop_start()
        if result != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError("MQTT network loop failed to start")

    def publish(self, publication: MqttPublication) -> MqttPublishReceipt:
        result = self._client.publish(
            publication.topic,
            publication.payload,
            qos=publication.qos,
            retain=publication.retain,
        )
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError("MQTT publish was not accepted by the client")
        return _PahoPublishReceipt(result)

    def subscribe(self, topic: str, qos: int, handler: MessageHandler) -> None:
        if not topic or "+" in topic or "#" in topic:
            raise ValueError("MQTT subscription topic must be exact and non-empty")
        if qos not in {0, 1, 2}:
            raise ValueError("MQTT subscription QoS must be 0, 1, or 2")
        previous_handler = self._message_handlers.get(topic)
        self._message_handlers[topic] = handler
        result, _message_id = self._client.subscribe(topic, qos=qos)
        if result != mqtt.MQTT_ERR_SUCCESS:
            if previous_handler is None:
                self._message_handlers.pop(topic, None)
            else:
                self._message_handlers[topic] = previous_handler
            raise RuntimeError("MQTT subscription was not accepted by the client")

    def disconnect(self) -> None:
        self._client.disconnect()
        self._client.loop_stop()

    def _handle_connect(
        self,
        client: Any,
        userdata: Any,
        flags: Any,
        reason_code: Any,
        properties: Any,
    ) -> None:
        del client, userdata, flags, properties
        if getattr(reason_code, "is_failure", True):
            self._logger.warning(
                "mqtt_connection_rejected",
                extra={"event": "mqtt_connection_rejected"},
            )
            self._on_disconnected()
            return
        self._on_connected()

    def _handle_connect_fail(self, client: Any, userdata: Any) -> None:
        del client, userdata
        self._logger.warning(
            "mqtt_connection_attempt_failed",
            extra={"event": "mqtt_connection_attempt_failed"},
        )
        self._on_disconnected()

    def _handle_disconnect(
        self,
        client: Any,
        userdata: Any,
        disconnect_flags: Any,
        reason_code: Any,
        properties: Any,
    ) -> None:
        del client, userdata, disconnect_flags, reason_code, properties
        self._on_disconnected()

    def _handle_message(self, client: Any, userdata: Any, message: Any) -> None:
        del client, userdata
        handler = self._message_handlers.get(message.topic)
        if handler is None:
            self._logger.warning(
                "mqtt_unhandled_message",
                extra={"event": "mqtt_unhandled_message", "topic": message.topic},
            )
            return
        handler(
            ReceivedMqttMessage(
                topic=message.topic,
                payload=bytes(message.payload),
                qos=message.qos,
                retain=message.retain,
            )
        )


class _PahoPublishReceipt:
    def __init__(self, message_info: Any) -> None:
        self._message_info = message_info

    def wait_for_confirmation(self, timeout_seconds: float) -> bool:
        if timeout_seconds <= 0:
            raise ValueError("MQTT confirmation timeout must be positive")
        try:
            self._message_info.wait_for_publish(timeout=timeout_seconds)
            return bool(self._message_info.is_published())
        except (RuntimeError, ValueError):
            return False
