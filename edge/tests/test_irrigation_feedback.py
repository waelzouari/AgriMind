from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from agrimind_edge.adapters.fake import FakeMqttTransport
from agrimind_edge.application.irrigation_feedback import IrrigationResultPublisher
from agrimind_edge.contracts import IrrigationResult, TopicBuilder
from agrimind_edge.contracts.enums import IrrigationOutcome
from agrimind_edge.domain.mqtt import MqttPublication
from agrimind_edge.domain.persistence import EdgeEvent, EdgeEventType

NOW = datetime(2026, 9, 24, 12, tzinfo=UTC)
FARM_ID = UUID("11111111-1111-4111-8111-111111111111")
DEVICE_ID = UUID("22222222-2222-4222-8222-222222222222")


class RecordingDurablePublisher:
    def __init__(self) -> None:
        self.submissions: list[tuple[EdgeEvent, MqttPublication, bool]] = []

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
        del replay_delivered
        self.submissions.append((event, publication, attempt_now))
        return True

    def request_drain(self) -> None:
        pass


def measured_result() -> IrrigationResult:
    return IrrigationResult(
        UUID("33333333-3333-4333-8333-333333333333"),
        FARM_ID,
        DEVICE_ID,
        42.0,
        46.5,
        4.5,
        IrrigationOutcome.INCREASED,
        NOW,
    )


def test_publisher_only_persists_a_prevalidated_measured_result() -> None:
    transport = FakeMqttTransport()
    durable = RecordingDurablePublisher()
    publisher = IrrigationResultPublisher(
        transport,
        TopicBuilder(FARM_ID, DEVICE_ID),
        durable_publisher=durable,
    )

    assert publisher.publish(measured_result()) is True

    event, publication, attempt_now = durable.submissions[0]
    assert event.event_type is EdgeEventType.IRRIGATION_RESULT
    assert event.event_id == measured_result().event_id
    assert publication.topic.endswith("/events/irrigation_result")
    assert publication.qos == 1
    assert publication.retain is False
    assert attempt_now is True


def test_publisher_rejects_cross_device_result() -> None:
    publisher = IrrigationResultPublisher(FakeMqttTransport(), TopicBuilder(FARM_ID, UUID(int=9)))

    with pytest.raises(ValueError, match="target differs"):
        publisher.publish(measured_result())


def test_no_acknowledgement_can_be_converted_to_agronomic_result() -> None:
    """The API accepts IrrigationResult only; lifecycle conversion does not exist."""

    assert not hasattr(IrrigationResultPublisher, "publish_acknowledgement_as_result")
