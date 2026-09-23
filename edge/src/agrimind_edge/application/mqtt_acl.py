"""Vendor-neutral exact-topic ACL policy for one edge device identity."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from agrimind_edge.contracts.enums import TelemetryMetric
from agrimind_edge.contracts.topics import TopicBuilder


@dataclass(frozen=True, slots=True)
class DeviceAclPolicy:
    topics: TopicBuilder

    @property
    def publish_topics(self) -> frozenset[str]:
        return frozenset(
            {
                self.topics.device_status(),
                *(self.topics.telemetry(metric) for metric in TelemetryMetric),
            }
        )

    @property
    def subscribe_topics(self) -> frozenset[str]:
        """Allow only the device's exact AGM-007 command topic."""

        return frozenset({self.topics.pump_command()})

    @property
    def acknowledgement_filter(self) -> str:
        """Broker ACL filter for per-command acknowledgement publications."""

        return f"{self.topics.base}/acks/+"

    def can_publish(self, topic: str) -> bool:
        if topic in self.publish_topics:
            return True
        prefix = f"{self.topics.base}/acks/"
        if not topic.startswith(prefix):
            return False
        suffix = topic.removeprefix(prefix)
        try:
            command_id = UUID(suffix)
        except ValueError:
            return False
        return command_id.int != 0 and str(command_id) == suffix

    def can_subscribe(self, topic: str) -> bool:
        return topic in self.subscribe_topics
