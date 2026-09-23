from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import paho.mqtt.client as mqtt
import pytest

from agrimind_ingestion.adapters.mqtt import (
    STATUS_FILTER,
    TELEMETRY_FILTER,
    PahoIngestionConsumer,
)
from agrimind_ingestion.domain import IngestionOutcome, IngestionResult


class FakeContext:
    minimum_version: object
    check_hostname: bool
    verify_mode: object


class FakeClient:
    def __init__(self) -> None:
        self.credentials: tuple[str, str] | None = None
        self.context: FakeContext | None = None
        self.manual_ack = False
        self.subscriptions: list[tuple[str, int]] = []
        self.acknowledgements: list[tuple[int, int]] = []
        self.disconnected = False
        self.on_connect: Any = None
        self.on_connect_fail: Any = None
        self.on_disconnect: Any = None
        self.on_message: Any = None

    def username_pw_set(self, username: str, password: str) -> None:
        self.credentials = (username, password)

    def tls_set_context(self, context: FakeContext) -> None:
        self.context = context

    def manual_ack_set(self, enabled: bool) -> None:
        self.manual_ack = enabled

    def reconnect_delay_set(self, *, min_delay: int, max_delay: int) -> None:
        assert (min_delay, max_delay) == (1, 60)

    def connect_async(self, host: str, port: int, *, keepalive: int) -> None:
        assert (host, port, keepalive) == ("mqtt.example.invalid", 8883, 60)

    def loop_start(self) -> int:
        return mqtt.MQTT_ERR_SUCCESS

    def loop_stop(self) -> None:
        pass

    def disconnect(self) -> None:
        self.disconnected = True

    def subscribe(self, topic: str, *, qos: int) -> tuple[int, int]:
        self.subscriptions.append((topic, qos))
        return mqtt.MQTT_ERR_SUCCESS, 1

    def ack(self, message_id: int, qos: int) -> int:
        self.acknowledgements.append((message_id, qos))
        return mqtt.MQTT_ERR_SUCCESS


class Processor:
    def __init__(self, result: IngestionResult) -> None:
        self.result = result

    def process(self, topic: str, payload: bytes, *, qos: int, retain: bool) -> IngestionResult:
        del topic, payload, qos, retain
        return self.result


def consumer(client: FakeClient, result: IngestionResult) -> PahoIngestionConsumer:
    return PahoIngestionConsumer(
        host="mqtt.example.invalid",
        port=8883,
        client_id="stable-ingestion-id",
        username="server-user",
        password="server-password",  # pragma: allowlist secret
        ca_file=Path("/absolute/ca.pem"),
        processor=Processor(result),
        client=client,
        ssl_context_factory=lambda **kwargs: FakeContext(),
    )


def test_default_client_uses_stable_id_and_persistent_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: dict[str, Any] = {}
    client = FakeClient()

    def factory(*args: object, **kwargs: object) -> FakeClient:
        created.update(kwargs)
        return client

    monkeypatch.setattr(mqtt, "Client", factory)
    PahoIngestionConsumer(
        host="mqtt.example.invalid",
        port=8883,
        client_id="stable-ingestion-id",
        username="server-user",
        password="server-password",  # pragma: allowlist secret
        ca_file=Path("/absolute/ca.pem"),
        processor=Processor(IngestionResult(IngestionOutcome.INSERTED, "inserted")),
        ssl_context_factory=lambda **kwargs: FakeContext(),
    )

    assert created["client_id"] == "stable-ingestion-id"
    assert created["clean_session"] is False
    assert created["protocol"] == mqtt.MQTTv311


def test_verified_tls_manual_ack_and_required_subscriptions() -> None:
    client = FakeClient()
    instance = consumer(client, IngestionResult(IngestionOutcome.INSERTED, "inserted"))
    reason = SimpleNamespace(is_failure=False)

    instance._on_connect(client, None, None, reason, None)

    assert client.manual_ack is True
    assert client.context is not None
    assert client.context.check_hostname is True
    assert client.context.verify_mode == 2
    assert client.subscriptions == [(TELEMETRY_FILTER, 1), (STATUS_FILTER, 1)]


def test_terminal_result_is_acked_and_retryable_result_disconnects_without_ack() -> None:
    message = SimpleNamespace(topic="topic", payload=b"payload", qos=1, retain=False, mid=7)
    accepted_client = FakeClient()
    consumer(
        accepted_client,
        IngestionResult(IngestionOutcome.DUPLICATE, "duplicate"),
    )._on_message(accepted_client, None, message)
    assert accepted_client.acknowledgements == [(7, 1)]

    retry_client = FakeClient()
    consumer(
        retry_client,
        IngestionResult(IngestionOutcome.RETRYABLE, "persistence_unavailable"),
    )._on_message(retry_client, None, message)
    assert retry_client.acknowledgements == []
    assert retry_client.disconnected is True
