"""Fail-fast runtime configuration with isolated, redacted MQTT secrets."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

from agrimind_edge.config.hardware import HardwareConfig
from agrimind_edge.contracts.models import MAX_PUMP_DURATION_SECONDS
from agrimind_edge.contracts.validation import TOPIC_VERSION, parse_uuid

_HOST_PATTERN = re.compile(r"^[a-zA-Z0-9](?:[a-zA-Z0-9.-]{0,251}[a-zA-Z0-9])?$")


def _required(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


def _integer(environment: Mapping[str, str], name: str, default: int) -> int:
    value = environment.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer") from error


def _boolean(environment: Mapping[str, str], name: str, default: bool) -> bool:
    value = environment.get(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized not in {"true", "false"}:
        raise ValueError(f"{name} must be true or false")
    return normalized == "true"


@dataclass(frozen=True, slots=True)
class MqttCredentials:
    """Secrets whose repr never reveals the supplied values."""

    username: str = field(repr=False)
    password: str = field(repr=False)

    def __post_init__(self) -> None:
        if not self.username or not self.password:
            raise ValueError("MQTT username and password are required")

    def __repr__(self) -> str:
        return "MqttCredentials(username='***', password='***')"


@dataclass(frozen=True, slots=True)
class MqttConfig:
    farm_id: UUID
    device_id: UUID
    host: str
    port: int = 8883
    tls_enabled: bool = True
    ca_file: Path | None = None
    telemetry_interval_seconds: int = 5
    keepalive_seconds: int = 60
    reconnect_min_seconds: int = 1
    reconnect_max_seconds: int = 60
    contract_version: str = TOPIC_VERSION

    def __post_init__(self) -> None:
        if self.farm_id.int == 0 or self.device_id.int == 0:
            raise ValueError("farm_id and device_id must be non-zero UUIDs")
        if not _HOST_PATTERN.fullmatch(self.host):
            raise ValueError("MQTT host must be a hostname or IPv4 literal without a scheme/path")
        if not 1 <= self.port <= 65_535:
            raise ValueError("MQTT port must be between 1 and 65535")
        if not 1 <= self.telemetry_interval_seconds <= 3_600:
            raise ValueError("telemetry interval must be between 1 and 3600 seconds")
        if not 10 <= self.keepalive_seconds <= 3_600:
            raise ValueError("MQTT keepalive must be between 10 and 3600 seconds")
        if not 1 <= self.reconnect_min_seconds <= self.reconnect_max_seconds <= 3_600:
            raise ValueError("MQTT reconnect delays must satisfy 1 <= minimum <= maximum <= 3600")
        if self.contract_version != TOPIC_VERSION:
            raise ValueError(f"unsupported contract version: {self.contract_version}")
        if self.tls_enabled and self.ca_file is None:
            raise ValueError("a CA file is required when MQTT TLS is enabled")
        if self.ca_file is not None and not self.ca_file.is_absolute():
            raise ValueError("MQTT CA file must use an absolute path")


@dataclass(frozen=True, slots=True)
class PumpSafetyConfig:
    """Local identity and duration limit enforced before pump actuation."""

    farm_id: UUID
    device_id: UUID
    max_duration_seconds: int = MAX_PUMP_DURATION_SECONDS

    def __post_init__(self) -> None:
        if self.farm_id.int == 0 or self.device_id.int == 0:
            raise ValueError("pump safety farm_id and device_id must be non-zero UUIDs")
        if not 1 <= self.max_duration_seconds <= MAX_PUMP_DURATION_SECONDS:
            raise ValueError(
                f"pump maximum duration must be between 1 and {MAX_PUMP_DURATION_SECONDS} seconds"
            )


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    mqtt: MqttConfig
    pump_safety: PumpSafetyConfig
    credentials: MqttCredentials = field(repr=False)
    hardware: HardwareConfig = field(default_factory=HardwareConfig)

    def __repr__(self) -> str:
        return (
            f"RuntimeConfig(mqtt={self.mqtt!r}, pump_safety={self.pump_safety!r}, "
            f"credentials={self.credentials!r}, hardware={self.hardware!r})"
        )

    @classmethod
    def from_environment(cls, environment: Mapping[str, str]) -> RuntimeConfig:
        """Validate one process environment while maintaining secret boundaries."""

        farm_id = parse_uuid(_required(environment, "AGRIMIND_FARM_ID"), "AGRIMIND_FARM_ID")
        device_id = parse_uuid(
            _required(environment, "AGRIMIND_DEVICE_ID"), "AGRIMIND_DEVICE_ID"
        )
        tls_enabled = _boolean(environment, "AGRIMIND_MQTT_TLS_ENABLED", True)
        ca_value = environment.get("AGRIMIND_MQTT_CA_FILE", "").strip()
        mqtt = MqttConfig(
            farm_id=farm_id,
            device_id=device_id,
            host=_required(environment, "AGRIMIND_MQTT_HOST"),
            port=_integer(environment, "AGRIMIND_MQTT_PORT", 8883),
            tls_enabled=tls_enabled,
            ca_file=Path(ca_value) if ca_value else None,
            telemetry_interval_seconds=_integer(
                environment, "AGRIMIND_TELEMETRY_INTERVAL_SECONDS", 5
            ),
            keepalive_seconds=_integer(environment, "AGRIMIND_MQTT_KEEPALIVE_SECONDS", 60),
            reconnect_min_seconds=_integer(
                environment, "AGRIMIND_MQTT_RECONNECT_MIN_SECONDS", 1
            ),
            reconnect_max_seconds=_integer(
                environment, "AGRIMIND_MQTT_RECONNECT_MAX_SECONDS", 60
            ),
            contract_version=environment.get(
                "AGRIMIND_CONTRACT_VERSION", TOPIC_VERSION
            ).strip(),
        )
        credentials = MqttCredentials(
            username=_required(environment, "AGRIMIND_MQTT_USERNAME"),
            password=_required(environment, "AGRIMIND_MQTT_PASSWORD"),
        )
        return cls(
            mqtt=mqtt,
            pump_safety=PumpSafetyConfig(
                farm_id=farm_id,
                device_id=device_id,
                max_duration_seconds=_integer(
                    environment,
                    "AGRIMIND_PUMP_MAX_DURATION_SECONDS",
                    MAX_PUMP_DURATION_SECONDS,
                ),
            ),
            credentials=credentials,
            hardware=HardwareConfig.from_environment(environment),
        )
