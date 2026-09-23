"""Broker-neutral MQTT transport and runtime status types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from agrimind_edge.contracts.enums import DeviceHealth


class MqttConnectionState(StrEnum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    STOPPED = "stopped"


@dataclass(frozen=True, slots=True)
class MqttPublication:
    topic: str
    payload: str
    qos: int
    retain: bool

    def __post_init__(self) -> None:
        if not self.topic or "+" in self.topic or "#" in self.topic:
            raise ValueError("publication topic must be an exact non-empty topic")
        if not self.payload:
            raise ValueError("publication payload must not be empty")
        if self.qos not in {0, 1, 2}:
            raise ValueError("MQTT QoS must be 0, 1, or 2")


@dataclass(frozen=True, slots=True)
class ReceivedMqttMessage:
    topic: str
    payload: bytes
    qos: int
    retain: bool

    def __post_init__(self) -> None:
        if not self.topic or "+" in self.topic or "#" in self.topic:
            raise ValueError("received MQTT topic must be exact and non-empty")
        if self.qos not in {0, 1, 2}:
            raise ValueError("received MQTT QoS must be 0, 1, or 2")


@dataclass(frozen=True, slots=True)
class DeviceRuntimeStatus:
    pump_state: bool
    health: DeviceHealth
    uptime_seconds: int
    firmware_version: str
    errors: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.uptime_seconds < 0:
            raise ValueError("uptime_seconds must be non-negative")
        if not self.firmware_version or len(self.firmware_version) > 64:
            raise ValueError("firmware_version must contain 1 to 64 characters")
        if len(self.errors) > 15:
            raise ValueError("runtime status supports at most 15 errors")


@dataclass(frozen=True, slots=True)
class TelemetryPublishResult:
    mapped: int
    published: int
    skipped_unavailable: int
    connection_state: MqttConnectionState
