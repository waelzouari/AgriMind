"""Deterministic MQTT transport and device-status fakes."""

from __future__ import annotations

from agrimind_edge.application.mqtt_ports import ConnectionHandler, DisconnectionHandler
from agrimind_edge.domain.mqtt import DeviceRuntimeStatus, MqttPublication


class FakeMqttTransport:
    def __init__(
        self,
        *,
        auto_connect: bool = True,
        connect_failure: Exception | None = None,
        fail_publish_at: set[int] | None = None,
    ) -> None:
        self.auto_connect = auto_connect
        self.connect_failure = connect_failure
        self.fail_publish_at = fail_publish_at or set()
        self.operations: list[str] = []
        self.publications: list[MqttPublication] = []
        self.last_will: MqttPublication | None = None
        self._on_connected: ConnectionHandler = lambda: None
        self._on_disconnected: DisconnectionHandler = lambda: None
        self._publish_attempts = 0

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
            self._on_connected()

    def publish(self, publication: MqttPublication) -> None:
        self._publish_attempts += 1
        self.operations.append("publish")
        if self._publish_attempts in self.fail_publish_at:
            raise RuntimeError("scripted MQTT publish failure")
        self.publications.append(publication)

    def disconnect(self) -> None:
        self.operations.append("disconnect")

    def simulate_disconnect(self) -> None:
        self.operations.append("simulate_disconnect")
        self._on_disconnected()

    def simulate_reconnect(self) -> None:
        self.operations.append("simulate_reconnect")
        self._on_connected()


class FakeDeviceStatusSource:
    def __init__(self, status: DeviceRuntimeStatus) -> None:
        self.status = status
        self.read_count = 0

    def read_status(self) -> DeviceRuntimeStatus:
        self.read_count += 1
        return self.status
