"""The single canonical constructor for lowercase AgriMind v1 topics."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from agrimind_edge.contracts.enums import TelemetryMetric
from agrimind_edge.contracts.validation import TOPIC_VERSION


@dataclass(frozen=True, slots=True)
class TopicBuilder:
    farm_id: UUID
    device_id: UUID
    version: str = TOPIC_VERSION

    def __post_init__(self) -> None:
        if self.farm_id.int == 0 or self.device_id.int == 0:
            raise ValueError("topic identifiers must be non-zero UUIDs")
        if self.version != TOPIC_VERSION:
            raise ValueError(f"unsupported topic version: {self.version}")

    @property
    def base(self) -> str:
        return (
            f"agrimind/{self.version}/farms/{self.farm_id}/devices/{self.device_id}"
        ).lower()

    def telemetry(self, metric: TelemetryMetric) -> str:
        return f"{self.base}/telemetry/{metric.value}"

    def pump_command(self) -> str:
        return f"{self.base}/commands/pump"

    def acknowledgement(self, command_id: UUID) -> str:
        if command_id.int == 0:
            raise ValueError("command_id must be a non-zero UUID")
        return f"{self.base}/acks/{command_id}"

    def device_status(self) -> str:
        return f"{self.base}/status/device"

    def irrigation_result(self) -> str:
        return f"{self.base}/events/irrigation_result"
