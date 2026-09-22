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


def test_agm006_grants_no_subscriptions_but_exposes_exact_future_command_topic() -> None:
    topics = TopicBuilder(UUID(int=1), UUID(int=2))
    policy = DeviceAclPolicy(topics)

    assert policy.subscribe_topics == frozenset()
    assert not policy.can_subscribe(topics.pump_command())
    assert policy.future_pump_command_topic == topics.pump_command()
