"""Eclipse Paho MQTT adapter with verified TLS and bounded reconnect backoff."""

from __future__ import annotations

import logging
import ssl
from collections.abc import Callable
from typing import Any

import paho.mqtt.client as mqtt

from agrimind_edge.application.mqtt_ports import ConnectionHandler, DisconnectionHandler
from agrimind_edge.config.runtime import MqttConfig, MqttCredentials
from agrimind_edge.domain.mqtt import MqttPublication


class PahoMqttTransport:
    """Keep all Paho-specific types inside the infrastructure adapter."""

    def __init__(
        self,
        config: MqttConfig,
        credentials: MqttCredentials,
        *,
        client: Any | None = None,
        ssl_context_factory: Callable[..., ssl.SSLContext] = ssl.create_default_context,
        logger: logging.Logger | None = None,
    ) -> None:
        if not config.tls_enabled or config.ca_file is None:
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

        self._client.username_pw_set(credentials.username, credentials.password)
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

    def publish(self, publication: MqttPublication) -> None:
        result = self._client.publish(
            publication.topic,
            publication.payload,
            qos=publication.qos,
            retain=publication.retain,
        )
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError("MQTT publish was not accepted by the client")

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
