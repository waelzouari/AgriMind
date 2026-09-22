from __future__ import annotations

import ssl
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import paho.mqtt.client as mqtt
import pytest

from agrimind_edge.adapters.mqtt import PahoMqttTransport
from agrimind_edge.config import MqttConfig, MqttCredentials
from agrimind_edge.domain import MqttPublication


class FakeSslContext:
    def __init__(self) -> None:
        self.minimum_version: ssl.TLSVersion | None = None
        self.check_hostname = False
        self.verify_mode: ssl.VerifyMode | None = None


class FakePahoClient:
    def __init__(self) -> None:
        self.operations: list[tuple[object, ...]] = []
        self.on_connect: Any = None
        self.on_connect_fail: Any = None
        self.on_disconnect: Any = None
        self.publish_rc = mqtt.MQTT_ERR_SUCCESS
        self.loop_start_rc = mqtt.MQTT_ERR_SUCCESS

    def username_pw_set(self, username: str, password: str) -> None:
        self.operations.append(("credentials", username, password))

    def tls_set_context(self, context: object) -> None:
        self.operations.append(("tls", context))

    def reconnect_delay_set(self, *, min_delay: int, max_delay: int) -> None:
        self.operations.append(("reconnect", min_delay, max_delay))

    def will_set(self, topic: str, payload: str, *, qos: int, retain: bool) -> None:
        self.operations.append(("will", topic, payload, qos, retain))

    def connect_async(self, host: str, port: int, *, keepalive: int) -> None:
        self.operations.append(("connect", host, port, keepalive))

    def loop_start(self) -> int:
        self.operations.append(("loop_start",))
        return self.loop_start_rc

    def publish(self, topic: str, payload: str, *, qos: int, retain: bool) -> object:
        self.operations.append(("publish", topic, payload, qos, retain))
        return SimpleNamespace(rc=self.publish_rc)

    def disconnect(self) -> None:
        self.operations.append(("disconnect",))

    def loop_stop(self) -> None:
        self.operations.append(("loop_stop",))


def config(
    *,
    tls_enabled: bool = True,
    ca_file: Path | None = Path("/tmp/test-ca.pem"),
) -> MqttConfig:
    return MqttConfig(
        farm_id=UUID(int=1),
        device_id=UUID(int=2),
        host="mqtt.example.invalid",
        tls_enabled=tls_enabled,
        ca_file=ca_file,
        keepalive_seconds=45,
        reconnect_min_seconds=2,
        reconnect_max_seconds=32,
    )


def test_adapter_configures_credentials_verified_tls_and_bounded_backoff() -> None:
    client = FakePahoClient()
    context = FakeSslContext()
    requested_ca_files: list[str] = []

    def context_factory(*, cafile: str) -> Any:
        requested_ca_files.append(cafile)
        return context

    PahoMqttTransport(
        config(),
        MqttCredentials("placeholder-user", "placeholder-password"),
        client=client,
        ssl_context_factory=context_factory,
    )

    assert requested_ca_files == ["/tmp/test-ca.pem"]
    assert context.minimum_version is ssl.TLSVersion.TLSv1_2
    assert context.check_hostname is True
    assert context.verify_mode is ssl.CERT_REQUIRED
    assert client.operations == [
        ("credentials", "placeholder-user", "placeholder-password"),
        ("tls", context),
        ("reconnect", 2, 32),
    ]
    assert "RPi.GPIO" not in sys.modules


def test_last_will_must_be_configured_before_connect() -> None:
    client = FakePahoClient()
    transport = PahoMqttTransport(
        config(),
        MqttCredentials("placeholder-user", "placeholder-password"),
        client=client,
        ssl_context_factory=lambda **kwargs: FakeSslContext(),
    )

    with pytest.raises(RuntimeError, match="last will"):
        transport.connect()

    publication = MqttPublication("exact/status", "{}", 1, True)
    transport.configure_last_will(publication)
    transport.connect()

    operation_names = [operation[0] for operation in client.operations]
    assert operation_names.index("will") < operation_names.index("connect")
    assert ("connect", "mqtt.example.invalid", 8883, 45) in client.operations


def test_adapter_forwards_connection_recovery_and_publication() -> None:
    client = FakePahoClient()
    transport = PahoMqttTransport(
        config(),
        MqttCredentials("placeholder-user", "placeholder-password"),
        client=client,
        ssl_context_factory=lambda **kwargs: FakeSslContext(),
    )
    events: list[str] = []
    transport.set_connection_handlers(
        lambda: events.append("connected"),
        lambda: events.append("disconnected"),
    )
    transport.configure_last_will(MqttPublication("exact/status", "{}", 1, True))
    transport.connect()

    client.on_connect(None, None, None, SimpleNamespace(is_failure=False), None)
    client.on_disconnect(None, None, None, None, None)
    client.on_connect(None, None, None, SimpleNamespace(is_failure=False), None)
    transport.publish(MqttPublication("exact/telemetry", "{}", 1, False))

    assert events == ["connected", "disconnected", "connected"]
    assert ("publish", "exact/telemetry", "{}", 1, False) in client.operations


def test_rejected_connection_reports_disconnected_state() -> None:
    client = FakePahoClient()
    transport = PahoMqttTransport(
        config(),
        MqttCredentials("placeholder-user", "placeholder-password"),
        client=client,
        ssl_context_factory=lambda **kwargs: FakeSslContext(),
    )
    events: list[str] = []
    transport.set_connection_handlers(
        lambda: events.append("connected"),
        lambda: events.append("disconnected"),
    )

    client.on_connect(None, None, None, SimpleNamespace(is_failure=True), None)

    assert events == ["disconnected"]


def test_adapter_rejects_unverified_cloud_configuration() -> None:
    credentials = MqttCredentials("placeholder-user", "placeholder-password")

    with pytest.raises(ValueError, match="verified TLS"):
        PahoMqttTransport(config(tls_enabled=False, ca_file=None), credentials)


def test_adapter_reports_client_publish_failure() -> None:
    client = FakePahoClient()
    client.publish_rc = mqtt.MQTT_ERR_NO_CONN
    transport = PahoMqttTransport(
        config(),
        MqttCredentials("placeholder-user", "placeholder-password"),
        client=client,
        ssl_context_factory=lambda **kwargs: FakeSslContext(),
    )

    with pytest.raises(RuntimeError, match="not accepted"):
        transport.publish(MqttPublication("exact/telemetry", "{}", 1, False))
