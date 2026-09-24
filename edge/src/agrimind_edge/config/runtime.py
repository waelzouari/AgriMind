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
from agrimind_edge.domain.broker import FailoverPolicy

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
class PersistenceConfig:
    """Local SQLite path; data retention remains an application invariant."""

    database_path: Path = Path("/var/lib/agrimind/edge.sqlite3")

    def __post_init__(self) -> None:
        if not self.database_path.is_absolute():
            raise ValueError("SQLite database path must use an absolute path")


@dataclass(frozen=True, slots=True)
class InferenceConfig:
    """Freshness policy for advisory local irrigation inference."""

    max_age_seconds: int = 30

    def __post_init__(self) -> None:
        if not 1 <= self.max_age_seconds <= 3_600:
            raise ValueError("inference maximum age must be between 1 and 3600 seconds")


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    mqtt: MqttConfig
    pump_safety: PumpSafetyConfig
    credentials: MqttCredentials = field(repr=False)
    hardware: HardwareConfig = field(default_factory=HardwareConfig)
    persistence: PersistenceConfig = field(default_factory=PersistenceConfig)
    local_mqtt: MqttConfig | None = None
    local_credentials: MqttCredentials | None = field(default=None, repr=False)
    failover: FailoverPolicy = field(default_factory=FailoverPolicy)
    inference: InferenceConfig = field(default_factory=InferenceConfig)

    def __repr__(self) -> str:
        return (
            f"RuntimeConfig(mqtt={self.mqtt!r}, pump_safety={self.pump_safety!r}, "
            f"credentials={self.credentials!r}, hardware={self.hardware!r}, "
            f"persistence={self.persistence!r}, local_mqtt={self.local_mqtt!r}, "
            f"local_credentials={self.local_credentials!r}, failover={self.failover!r}, "
            f"inference={self.inference!r})"
        )

    @classmethod
    def from_environment(cls, environment: Mapping[str, str]) -> RuntimeConfig:
        """Validate one process environment while maintaining secret boundaries."""

        farm_id = parse_uuid(_required(environment, "AGRIMIND_FARM_ID"), "AGRIMIND_FARM_ID")
        device_id = parse_uuid(_required(environment, "AGRIMIND_DEVICE_ID"), "AGRIMIND_DEVICE_ID")
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
            reconnect_min_seconds=_integer(environment, "AGRIMIND_MQTT_RECONNECT_MIN_SECONDS", 1),
            reconnect_max_seconds=_integer(environment, "AGRIMIND_MQTT_RECONNECT_MAX_SECONDS", 60),
            contract_version=environment.get("AGRIMIND_CONTRACT_VERSION", TOPIC_VERSION).strip(),
        )
        credentials = MqttCredentials(
            username=_required(environment, "AGRIMIND_MQTT_USERNAME"),
            password=_required(environment, "AGRIMIND_MQTT_PASSWORD"),
        )
        failover = FailoverPolicy(
            enabled=_boolean(environment, "AGRIMIND_MQTT_FAILOVER_ENABLED", False),
            cloud_failure_threshold=_integer(
                environment, "AGRIMIND_MQTT_CLOUD_FAILURE_THRESHOLD", 3
            ),
            failover_delay_seconds=_integer(
                environment, "AGRIMIND_MQTT_FAILOVER_DELAY_SECONDS", 30
            ),
            local_min_active_seconds=_integer(
                environment, "AGRIMIND_MQTT_LOCAL_MIN_ACTIVE_SECONDS", 60
            ),
            cloud_probe_interval_seconds=_integer(
                environment, "AGRIMIND_MQTT_CLOUD_PROBE_INTERVAL_SECONDS", 30
            ),
            cloud_stability_seconds=_integer(
                environment, "AGRIMIND_MQTT_CLOUD_STABILITY_SECONDS", 30
            ),
        )
        local_mqtt = None
        local_credentials = None
        if failover.enabled:
            local_tls = _boolean(environment, "AGRIMIND_LOCAL_MQTT_TLS_ENABLED", False)
            local_ca = environment.get("AGRIMIND_LOCAL_MQTT_CA_FILE", "").strip()
            local_mqtt = MqttConfig(
                farm_id=farm_id,
                device_id=device_id,
                host=_required(environment, "AGRIMIND_LOCAL_MQTT_HOST"),
                port=_integer(environment, "AGRIMIND_LOCAL_MQTT_PORT", 1883),
                tls_enabled=local_tls,
                ca_file=Path(local_ca) if local_ca else None,
                telemetry_interval_seconds=mqtt.telemetry_interval_seconds,
                keepalive_seconds=mqtt.keepalive_seconds,
                reconnect_min_seconds=mqtt.reconnect_min_seconds,
                reconnect_max_seconds=mqtt.reconnect_max_seconds,
            )
            local_credentials = MqttCredentials(
                _required(environment, "AGRIMIND_LOCAL_MQTT_USERNAME"),
                _required(environment, "AGRIMIND_LOCAL_MQTT_PASSWORD"),
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
            persistence=PersistenceConfig(
                database_path=Path(
                    environment.get(
                        "AGRIMIND_SQLITE_PATH", "/var/lib/agrimind/edge.sqlite3"
                    ).strip()
                )
            ),
            local_mqtt=local_mqtt,
            local_credentials=local_credentials,
            failover=failover,
            inference=InferenceConfig(
                max_age_seconds=_integer(
                    environment,
                    "AGRIMIND_IRRIGATION_INFERENCE_MAX_AGE_SECONDS",
                    30,
                )
            ),
        )
