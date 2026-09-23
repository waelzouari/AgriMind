"""Broker-neutral ports for MQTT transport and device runtime state."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from agrimind_edge.domain.mqtt import (
    DeviceRuntimeStatus,
    MqttPublication,
    ReceivedMqttMessage,
)

ConnectionHandler = Callable[[], None]
DisconnectionHandler = Callable[[], None]
MessageHandler = Callable[[ReceivedMqttMessage], None]


class MqttTransport(Protocol):
    def set_connection_handlers(
        self,
        on_connected: ConnectionHandler,
        on_disconnected: DisconnectionHandler,
    ) -> None: ...

    def configure_last_will(self, publication: MqttPublication) -> None: ...

    def connect(self) -> None: ...

    def publish(self, publication: MqttPublication) -> None: ...

    def subscribe(self, topic: str, qos: int, handler: MessageHandler) -> None: ...

    def disconnect(self) -> None: ...


class DeviceStatusSource(Protocol):
    def read_status(self) -> DeviceRuntimeStatus: ...
