"""Validated server-only ingestion configuration with redacted secrets."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse


def _required(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


def _integer(environment: Mapping[str, str], name: str, default: int) -> int:
    raw = environment.get(name, str(default)).strip()
    try:
        return int(raw)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer") from error


@dataclass(frozen=True, slots=True)
class SecretValue:
    value: str = field(repr=False)

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("secret value must not be empty")

    def __repr__(self) -> str:
        return "SecretValue('***')"


@dataclass(frozen=True, slots=True)
class IngestionConfig:
    mqtt_host: str
    mqtt_port: int
    mqtt_client_id: str
    mqtt_username: SecretValue = field(repr=False)
    mqtt_password: SecretValue = field(repr=False)
    mqtt_ca_file: Path
    supabase_url: str
    supabase_service_role_key: SecretValue = field(repr=False)
    maximum_age: timedelta = timedelta(hours=24)
    maximum_future_skew: timedelta = timedelta(minutes=5)
    contract_root: Path = Path("contracts/v1")

    def __post_init__(self) -> None:
        if not self.mqtt_host or "://" in self.mqtt_host or "/" in self.mqtt_host:
            raise ValueError("MQTT host must not contain a URL scheme or path")
        if not 1 <= self.mqtt_port <= 65_535:
            raise ValueError("MQTT port must be between 1 and 65535")
        if not self.mqtt_client_id or len(self.mqtt_client_id) > 128:
            raise ValueError("MQTT client ID must contain 1 to 128 characters")
        if not self.mqtt_ca_file.is_absolute():
            raise ValueError("MQTT CA file must use an absolute path")
        parsed_url = urlparse(self.supabase_url)
        if (
            parsed_url.scheme != "https"
            or not parsed_url.netloc
            or parsed_url.path not in {"", "/"}
        ):
            raise ValueError("Supabase URL must be an HTTPS origin without a path")
        if self.maximum_age <= timedelta(0):
            raise ValueError("maximum telemetry age must be positive")
        if self.maximum_future_skew < timedelta(0):
            raise ValueError("maximum future clock skew must not be negative")

    def __repr__(self) -> str:
        return (
            "IngestionConfig("
            f"mqtt_host={self.mqtt_host!r}, mqtt_port={self.mqtt_port!r}, "
            f"mqtt_client_id={self.mqtt_client_id!r}, mqtt_username=***, "
            f"mqtt_password=***, mqtt_ca_file={self.mqtt_ca_file!r}, "
            f"supabase_url={self.supabase_url!r}, supabase_service_role_key=***, "
            f"maximum_age={self.maximum_age!r}, "
            f"maximum_future_skew={self.maximum_future_skew!r}, "
            f"contract_root={self.contract_root!r})"
        )

    @classmethod
    def from_environment(cls, environment: Mapping[str, str]) -> IngestionConfig:
        repository_root = Path(__file__).resolve().parents[5]
        return cls(
            mqtt_host=_required(environment, "AGRIMIND_INGESTION_MQTT_HOST"),
            mqtt_port=_integer(environment, "AGRIMIND_INGESTION_MQTT_PORT", 8883),
            mqtt_client_id=_required(environment, "AGRIMIND_INGESTION_MQTT_CLIENT_ID"),
            mqtt_username=SecretValue(_required(environment, "AGRIMIND_INGESTION_MQTT_USERNAME")),
            mqtt_password=SecretValue(_required(environment, "AGRIMIND_INGESTION_MQTT_PASSWORD")),
            mqtt_ca_file=Path(_required(environment, "AGRIMIND_INGESTION_MQTT_CA_FILE")),
            supabase_url=_required(environment, "AGRIMIND_INGESTION_SUPABASE_URL"),
            supabase_service_role_key=SecretValue(
                _required(environment, "AGRIMIND_INGESTION_SUPABASE_SERVICE_ROLE_KEY")
            ),
            maximum_age=timedelta(
                seconds=_integer(environment, "AGRIMIND_INGESTION_MAXIMUM_AGE_SECONDS", 86_400)
            ),
            maximum_future_skew=timedelta(
                seconds=_integer(environment, "AGRIMIND_INGESTION_MAXIMUM_FUTURE_SKEW_SECONDS", 300)
            ),
            contract_root=Path(
                environment.get(
                    "AGRIMIND_INGESTION_CONTRACT_ROOT",
                    str(repository_root / "contracts" / "v1"),
                ).strip()
            ),
        )
