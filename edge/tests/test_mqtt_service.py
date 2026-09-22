from __future__ import annotations

from datetime import UTC, datetime
from itertools import count
from uuid import UUID

from agrimind_edge.adapters.fake import FakeDeviceStatusSource, FakeMqttTransport
from agrimind_edge.application import CloudMqttService, TelemetryMapper
from agrimind_edge.contracts.enums import DeviceHealth
from agrimind_edge.contracts.models import DeviceStatus, Telemetry
from agrimind_edge.contracts.topics import TopicBuilder
from agrimind_edge.domain import (
    DeviceRuntimeStatus,
    Measurement,
    MqttConnectionState,
    ReadingQuality,
    SensorSnapshot,
)

NOW = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)
FARM_ID = UUID("11111111-1111-4111-8111-111111111111")
DEVICE_ID = UUID("22222222-2222-4222-8222-222222222222")


def measurement(value: float | int, unit: str) -> Measurement:
    return Measurement(value, unit, ReadingQuality.VALID, NOW)


def snapshot() -> SensorSnapshot:
    return SensorSnapshot(
        NOW,
        "snapshot-006",
        measurement(24.5, "celsius"),
        measurement(62.0, "percent"),
        measurement(45.0, "percent"),
        measurement(20_350, "adc_raw"),
        measurement(8.0, "centimeter"),
        measurement(20.0, "centimeter"),
        measurement(66.7, "percent"),
    )


def make_service(
    transport: FakeMqttTransport,
) -> tuple[CloudMqttService, FakeDeviceStatusSource]:
    identifiers = count(100)
    source = FakeDeviceStatusSource(DeviceRuntimeStatus(False, DeviceHealth.HEALTHY, 3600, "0.0.0"))
    service = CloudMqttService(
        transport,
        TelemetryMapper(
            FARM_ID,
            DEVICE_ID,
            message_id_factory=lambda: UUID(int=next(identifiers)),
        ),
        TopicBuilder(FARM_ID, DEVICE_ID),
        source,
        clock=lambda: NOW,
        message_id_factory=lambda: UUID(int=next(identifiers)),
    )
    return service, source


def test_lwt_is_configured_before_connect_and_online_status_follows_connection() -> None:
    transport = FakeMqttTransport()
    service, _ = make_service(transport)

    service.start()

    assert transport.operations[:4] == [
        "set_connection_handlers",
        "configure_last_will",
        "connect",
        "publish",
    ]
    assert service.state is MqttConnectionState.CONNECTED
    assert transport.last_will is not None
    assert transport.last_will.qos == 1
    assert transport.last_will.retain is True
    assert transport.last_will.topic == TopicBuilder(FARM_ID, DEVICE_ID).device_status()
    offline = DeviceStatus.from_json(transport.last_will.payload)
    online = DeviceStatus.from_json(transport.publications[0].payload)
    assert offline.online is False
    assert offline.health is DeviceHealth.DEGRADED
    assert offline.errors == ("mqtt_session_lost",)
    assert online.online is True
    assert online.health is DeviceHealth.HEALTHY
    assert online.errors == ()
    assert transport.publications[0].retain is True
    assert transport.publications[0].qos == 1


def test_publishes_contract_telemetry_qos_one_without_retention() -> None:
    transport = FakeMqttTransport()
    service, _ = make_service(transport)
    service.start()

    result = service.publish_snapshot(snapshot())

    telemetry_messages = transport.publications[1:]
    assert result.mapped == 4
    assert result.published == 4
    assert result.skipped_unavailable == 0
    assert len(telemetry_messages) == 4
    assert all(message.qos == 1 for message in telemetry_messages)
    assert all(message.retain is False for message in telemetry_messages)
    parsed = [Telemetry.from_json(message.payload) for message in telemetry_messages]
    assert [message.topic for message in telemetry_messages] == [
        TopicBuilder(FARM_ID, DEVICE_ID).telemetry(item.metric) for item in parsed
    ]


def test_broker_unavailable_does_not_crash_or_publish() -> None:
    transport = FakeMqttTransport(connect_failure=OSError("broker unavailable"))
    service, _ = make_service(transport)

    service.start()
    result = service.publish_snapshot(snapshot())

    assert service.state is MqttConnectionState.DISCONNECTED
    assert result.published == 0
    assert result.mapped == 4
    assert transport.publications == []


def test_disconnect_and_reconnect_republish_online_presence() -> None:
    transport = FakeMqttTransport()
    service, _ = make_service(transport)
    service.start()
    transport.simulate_disconnect()

    offline_result = service.publish_snapshot(snapshot())
    transport.simulate_reconnect()

    assert offline_result.published == 0
    assert service.state is MqttConnectionState.CONNECTED
    statuses = [
        DeviceStatus.from_json(message.payload)
        for message in transport.publications
        if message.topic.endswith("/status/device")
    ]
    assert [status.online for status in statuses] == [True, True]


def test_one_publish_failure_does_not_abort_remaining_metrics() -> None:
    transport = FakeMqttTransport(fail_publish_at={3})
    service, _ = make_service(transport)
    service.start()  # attempt 1 is online status

    result = service.publish_snapshot(snapshot())

    assert result.mapped == 4
    assert result.published == 3
    assert len(transport.publications) == 4  # online plus three telemetry messages


def test_graceful_stop_publishes_retained_offline_without_session_loss_error() -> None:
    transport = FakeMqttTransport()
    service, _ = make_service(transport)
    service.start()

    service.stop()

    status = DeviceStatus.from_json(transport.publications[-1].payload)
    assert status.online is False
    assert status.health is DeviceHealth.HEALTHY
    assert status.errors == ()
    assert transport.publications[-1].retain is True
    assert service.state is MqttConnectionState.STOPPED


def test_mqtt_path_has_no_pump_capability() -> None:
    transport = FakeMqttTransport()
    service, _ = make_service(transport)

    assert not hasattr(service, "pump")
    assert not hasattr(transport, "turn_on")
    assert not hasattr(transport, "turn_off")
