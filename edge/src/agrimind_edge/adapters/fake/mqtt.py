"""Deterministic MQTT transport and device-status fakes."""

from __future__ import annotations

from agrimind_edge.application.mqtt_ports import (
    ConnectionHandler,
    DisconnectionHandler,
    MessageHandler,
    MqttPublishReceipt,
)
from agrimind_edge.domain.mqtt import (
    DeviceRuntimeStatus,
    MqttPublication,
    ReceivedMqttMessage,
)


class FakeMqttTransport:
    def __init__(
        self,
        *,
        auto_connect: bool = True,
        connect_failure: Exception | None = None,
        fail_publish_at: set[int] | None = None,
        unconfirmed_publish_at: set[int] | None = None,
    ) -> None:
        self.auto_connect = auto_connect
        self.connect_failure = connect_failure
        self.fail_publish_at = fail_publish_at or set()
        self.unconfirmed_publish_at = unconfirmed_publish_at or set()
        self.operations: list[str] = []
        self.publications: list[MqttPublication] = []
        self.last_will: MqttPublication | None = None
        self.subscriptions: list[tuple[str, int]] = []
        self._active_subscriptions: dict[str, MessageHandler] = {}
        self._on_connected: ConnectionHandler = lambda: None
        self._on_disconnected: DisconnectionHandler = lambda: None
        self._publish_attempts = 0
        self._connected = False

    def set_connection_handlers(
        self,
        on_connected: ConnectionHandler,
        on_disconnected: DisconnectionHandler,
    ) -> None:
        self._on_connected = on_connected
        self._on_disconnected = on_disconnected
        self.operations.append("set_connection_handlers")

    def configure_last_will(self, publication: MqttPublication) -> None:
        self.last_will = publication
        self.operations.append("configure_last_will")

    def connect(self) -> None:
        self.operations.append("connect")
        if self.connect_failure is not None:
            raise self.connect_failure
        if self.auto_connect:
            self._connected = True
            self._on_connected()

    def publish(self, publication: MqttPublication) -> MqttPublishReceipt:
        if not self._connected:
            raise RuntimeError("fake MQTT transport is disconnected")
        self._publish_attempts += 1
        self.operations.append("publish")
        if self._publish_attempts in self.fail_publish_at:
            raise RuntimeError("scripted MQTT publish failure")
        self.publications.append(publication)
        return FakeMqttPublishReceipt(
            confirmed=self._publish_attempts not in self.unconfirmed_publish_at
        )

    def subscribe(self, topic: str, qos: int, handler: MessageHandler) -> None:
        if not self._connected:
            raise RuntimeError("fake MQTT transport is disconnected")
        self.operations.append("subscribe")
        self.subscriptions.append((topic, qos))
        self._active_subscriptions[topic] = handler

    def disconnect(self) -> None:
        self.operations.append("disconnect")
        self._connected = False
        self._active_subscriptions.clear()

    def simulate_disconnect(self) -> None:
        self.operations.append("simulate_disconnect")
        self._connected = False
        self._active_subscriptions.clear()
        self._on_disconnected()

    def simulate_reconnect(self) -> None:
        self.operations.append("simulate_reconnect")
        self._connected = True
        self._on_connected()

    def simulate_message(self, message: ReceivedMqttMessage) -> None:
        if not self._connected:
            raise RuntimeError("cannot deliver MQTT message while disconnected")
        handler = self._active_subscriptions.get(message.topic)
        if handler is None:
            raise RuntimeError("no active subscription for MQTT message topic")
        self.operations.append("receive")
        handler(message)


class FakeDeviceStatusSource:
    def __init__(self, status: DeviceRuntimeStatus) -> None:
        self.status = status
        self.read_count = 0

    def read_status(self) -> DeviceRuntimeStatus:
        self.read_count += 1
        return self.status


class FakeMqttPublishReceipt:
    def __init__(self, *, confirmed: bool) -> None:
        self.confirmed = confirmed
        self.wait_count = 0

    def wait_for_confirmation(self, timeout_seconds: float) -> bool:
        if timeout_seconds <= 0:
            raise ValueError("MQTT confirmation timeout must be positive")
        self.wait_count += 1
        return self.confirmed
