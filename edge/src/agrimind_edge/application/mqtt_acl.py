"""Vendor-neutral exact-topic ACL policy for one edge device identity."""

from __future__ import annotations

from dataclasses import dataclass

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
        """AGM-006 is publish-only; it grants no subscriptions."""

        return frozenset()

    @property
    def future_pump_command_topic(self) -> str:
        """Exact future permission; not granted by AGM-006."""

        return self.topics.pump_command()

    def can_publish(self, topic: str) -> bool:
        return topic in self.publish_topics

    def can_subscribe(self, topic: str) -> bool:
        return topic in self.subscribe_topics
