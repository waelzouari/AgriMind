from uuid import UUID

from agrimind_edge.application import DeviceAclPolicy
from agrimind_edge.contracts.enums import TelemetryMetric
from agrimind_edge.contracts.topics import TopicBuilder


def test_device_acl_allows_only_exact_own_publish_topics() -> None:
    own = TopicBuilder(UUID(int=1), UUID(int=2))
    other = TopicBuilder(UUID(int=3), UUID(int=4))
    policy = DeviceAclPolicy(own)

    assert policy.can_publish(own.device_status())
    assert all(policy.can_publish(own.telemetry(metric)) for metric in TelemetryMetric)
    assert not policy.can_publish(other.device_status())
    assert not policy.can_publish(other.telemetry(TelemetryMetric.TEMPERATURE))
    assert not policy.can_publish(f"{own.base}/#")
    assert not policy.can_publish(own.pump_command())


def test_device_can_subscribe_only_to_own_command_and_ingestion_ack_topics() -> None:
    topics = TopicBuilder(UUID(int=1), UUID(int=2))
    other = TopicBuilder(UUID(int=3), UUID(int=4))
    policy = DeviceAclPolicy(topics)

    assert policy.subscribe_topics == frozenset(
        {topics.pump_command(), topics.ingestion_acknowledgement_filter()}
    )
    assert policy.can_subscribe(topics.pump_command())
    assert policy.can_subscribe(topics.ingestion_acknowledgement_filter())
    assert not policy.can_subscribe(other.pump_command())
    assert not policy.can_subscribe(other.ingestion_acknowledgement_filter())
    assert not policy.can_subscribe(f"{topics.base}/#")


def test_agm007_allows_only_canonical_own_ack_publications() -> None:
    topics = TopicBuilder(UUID(int=1), UUID(int=2))
    other = TopicBuilder(UUID(int=3), UUID(int=4))
    policy = DeviceAclPolicy(topics)
    command_id = UUID(int=10)

    assert policy.acknowledgement_filter == f"{topics.base}/acks/+"
    assert policy.can_publish(topics.acknowledgement(command_id))
    assert not policy.can_publish(other.acknowledgement(command_id))
    assert not policy.can_publish(f"{topics.base}/acks/not-a-uuid")
    assert not policy.can_publish(f"{topics.base}/acks/+")
