from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from agrimind_edge.adapters.fake import FakeMqttTransport, FakePump, FakeScheduler
from agrimind_edge.adapters.persistence import SqliteEventOutboxStore
from agrimind_edge.application import (
    MqttAcknowledgementPublisher,
    MqttPumpCommandProcessor,
    PumpCommandHandler,
    SafePumpController,
)
from agrimind_edge.application.mqtt_failover import FailoverEventPublisher, FailoverMqttTransport
from agrimind_edge.config import PumpSafetyConfig
from agrimind_edge.contracts import PumpCommand
from agrimind_edge.contracts.enums import PumpAction
from agrimind_edge.contracts.topics import TopicBuilder
from agrimind_edge.domain.broker import BrokerState, FailoverPolicy
from agrimind_edge.domain.mqtt import MqttPublication, ReceivedMqttMessage
from agrimind_edge.domain.persistence import EdgeEvent, EdgeEventType


class Clock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def make_router(
    *, enabled: bool = True
) -> tuple[FailoverMqttTransport, FakeMqttTransport, FakeMqttTransport, Clock]:
    cloud = FakeMqttTransport()
    local = FakeMqttTransport()
    clock = Clock()
    router = FailoverMqttTransport(
        cloud,
        local,
        FailoverPolicy(enabled, 3, 30, 60, 30, 30),
        monotonic=clock,
    )
    router.configure_last_will(MqttPublication("status", "{}", 1, True))
    return router, cloud, local, clock


def test_cloud_is_selected_initially() -> None:
    router, cloud, local, _ = make_router()
    connected: list[str] = []
    router.set_connection_handlers(lambda: connected.append("up"), lambda: None)
    router.connect()

    assert router.state is BrokerState.CLOUD_ACTIVE
    assert connected == ["up"]
    assert "connect" in cloud.operations
    assert "connect" not in local.operations


def test_threshold_and_delay_activate_local_fallback() -> None:
    router, cloud, local, clock = make_router()
    router.connect()
    for _ in range(3):
        cloud.simulate_disconnect()
    assert router.state is BrokerState.FAILOVER_PENDING
    router.evaluate()
    assert "connect" not in local.operations

    clock.advance(30)
    router.evaluate()

    assert router.state is BrokerState.LOCAL_FALLBACK
    assert "connect" in local.operations


def test_disabled_fallback_stays_offline() -> None:
    router, cloud, local, clock = make_router(enabled=False)
    router.connect()
    cloud.simulate_disconnect()
    clock.advance(300)
    router.evaluate()
    assert router.state is BrokerState.OFFLINE
    assert "connect" not in local.operations


def test_cloud_recovery_requires_stability_and_moves_subscription() -> None:
    router, cloud, local, clock = make_router()
    router.set_connection_handlers(
        lambda: router.subscribe("commands/pump", 1, lambda message: None),
        lambda: None,
    )
    router.connect()
    for _ in range(3):
        cloud.simulate_disconnect()
    clock.advance(30)
    router.evaluate()
    assert local.subscriptions == [("commands/pump", 1)]

    clock.advance(30)
    cloud.simulate_reconnect()
    assert router.state is BrokerState.CLOUD_RECOVERY
    clock.advance(29)
    router.evaluate()
    assert router.state is BrokerState.CLOUD_RECOVERY
    clock.advance(1)
    router.evaluate()

    assert router.state is BrokerState.CLOUD_ACTIVE
    assert local.operations[-1] == "disconnect"
    assert cloud.subscriptions[-1] == ("commands/pump", 1)


def test_publish_uses_only_active_broker() -> None:
    router, cloud, local, clock = make_router()
    publication = MqttPublication("telemetry", "{}", 1, False)
    router.connect()
    router.publish(publication)
    for _ in range(3):
        cloud.simulate_disconnect()
    clock.advance(30)
    router.evaluate()
    router.publish(publication)

    assert cloud.publications == [publication]
    assert local.publications == [publication]


class CloudOutboxSpy:
    def __init__(self) -> None:
        self.attempts: list[bool] = []
        self.drain_count = 0

    def initialize(self) -> bool:
        return True

    def submit(
        self,
        event: EdgeEvent,
        publication: MqttPublication,
        *,
        attempt_now: bool,
        replay_delivered: bool = False,
    ) -> bool:
        self.attempts.append(attempt_now)
        return False

    def request_drain(self) -> None:
        self.drain_count += 1


def test_local_puback_never_marks_cloud_outbox_delivered() -> None:
    router, cloud, local, clock = make_router()
    router.connect()
    for _ in range(3):
        cloud.simulate_disconnect()
    clock.advance(30)
    router.evaluate()
    outbox = CloudOutboxSpy()
    publisher = FailoverEventPublisher(outbox, local, router)
    publication = MqttPublication("telemetry", "{}", 1, False)
    event = EdgeEvent(
        UUID(int=1),
        EdgeEventType.TELEMETRY,
        UUID(int=2),
        UUID(int=3),
        datetime(2026, 9, 23, tzinfo=UTC),
        "{}",
    )

    assert publisher.submit(event, publication, attempt_now=True) is True
    assert outbox.attempts == [False]
    assert local.publications == [publication]
    publisher.request_drain()
    assert outbox.drain_count == 0


def test_same_command_across_cloud_and_local_never_actuates_twice(tmp_path: Path) -> None:
    router, cloud, local, clock = make_router()
    farm_id, device_id = UUID(int=2), UUID(int=3)
    topics = TopicBuilder(farm_id, device_id)
    store = SqliteEventOutboxStore(tmp_path / "edge.sqlite3")
    store.initialize()
    pump = FakePump()
    now = datetime(2026, 9, 23, 12, tzinfo=UTC)
    handler = PumpCommandHandler(
        SafePumpController(pump, FakeScheduler()),
        PumpSafetyConfig(farm_id, device_id),
        clock=lambda: now,
        processed_command_store=store,
    )
    processor = MqttPumpCommandProcessor(
        handler,
        MqttAcknowledgementPublisher(router, topics),
        topics,
        clock=lambda: now,
    )
    router.set_connection_handlers(
        lambda: router.subscribe(topics.pump_command(), 1, processor.process),
        lambda: None,
    )
    router.connect()
    command = PumpCommand(
        UUID(int=4),
        farm_id,
        device_id,
        PumpAction.ON,
        now - timedelta(seconds=1),
        now + timedelta(minutes=1),
        UUID(int=5),
        5,
    )
    message = ReceivedMqttMessage(topics.pump_command(), command.to_json().encode(), 1, False)
    cloud.simulate_message(message)
    for _ in range(3):
        cloud.simulate_disconnect()
    clock.advance(30)
    router.evaluate()
    local.simulate_message(message)

    assert pump.calls.count("turn_on") == 1
    assert len(cloud.publications) == 1
    assert len(local.publications) == 1
