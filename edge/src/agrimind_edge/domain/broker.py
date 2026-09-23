"""Deterministic broker-selection state for the MQTT fallback boundary."""

from dataclasses import dataclass
from enum import StrEnum


class BrokerState(StrEnum):
    OFFLINE = "offline"
    CLOUD_ACTIVE = "cloud_active"
    FAILOVER_PENDING = "failover_pending"
    LOCAL_FALLBACK = "local_fallback"
    CLOUD_RECOVERY = "cloud_recovery"


@dataclass(frozen=True, slots=True)
class FailoverPolicy:
    enabled: bool = False
    cloud_failure_threshold: int = 3
    failover_delay_seconds: int = 30
    local_min_active_seconds: int = 60
    cloud_probe_interval_seconds: int = 30
    cloud_stability_seconds: int = 30

    def __post_init__(self) -> None:
        if self.cloud_failure_threshold < 1:
            raise ValueError("cloud failure threshold must be positive")
        for name, value in (
            ("failover delay", self.failover_delay_seconds),
            ("local minimum active time", self.local_min_active_seconds),
            ("cloud probe interval", self.cloud_probe_interval_seconds),
            ("cloud stability time", self.cloud_stability_seconds),
        ):
            if value < 1:
                raise ValueError(f"{name} must be positive")
