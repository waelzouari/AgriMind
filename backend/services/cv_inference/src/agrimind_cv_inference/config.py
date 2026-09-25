"""Strict non-privileged CV service runtime configuration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse


def _required(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


@dataclass(frozen=True, slots=True)
class PublicKey:
    value: str = field(repr=False)

    def __repr__(self) -> str:
        return "PublicKey('***')"


@dataclass(frozen=True, slots=True)
class CvInferenceConfig:
    supabase_url: str
    supabase_publishable_key: PublicKey = field(repr=False)
    model_metadata: Path
    model_artifact: Path
    http_host: str = "127.0.0.1"
    http_port: int = 8080
    http_timeout_seconds: float = 10.0

    def __post_init__(self) -> None:
        parsed = urlparse(self.supabase_url)
        if parsed.scheme != "https" or not parsed.netloc or parsed.path not in {"", "/"}:
            raise ValueError("Supabase URL must be an HTTPS origin")
        if not self.model_metadata.is_absolute() or not self.model_artifact.is_absolute():
            raise ValueError("model paths must be absolute")
        if not 1 <= self.http_port <= 65535 or self.http_timeout_seconds <= 0:
            raise ValueError("HTTP configuration is invalid")

    @classmethod
    def from_environment(cls, environment: Mapping[str, str]) -> CvInferenceConfig:
        try:
            port = int(environment.get("AGRIMIND_CV_HTTP_PORT", "8080"))
            timeout = float(environment.get("AGRIMIND_CV_HTTP_TIMEOUT_SECONDS", "10"))
        except ValueError as error:
            raise ValueError("CV HTTP port and timeout must be numeric") from error
        return cls(
            _required(environment, "AGRIMIND_CV_SUPABASE_URL"),
            PublicKey(_required(environment, "AGRIMIND_CV_SUPABASE_PUBLISHABLE_KEY")),
            Path(_required(environment, "AGRIMIND_CV_MODEL_METADATA")),
            Path(_required(environment, "AGRIMIND_CV_MODEL_ARTIFACT")),
            environment.get("AGRIMIND_CV_HTTP_HOST", "127.0.0.1").strip(),
            port,
            timeout,
        )

    def __repr__(self) -> str:
        return (
            "CvInferenceConfig("
            f"supabase_url={self.supabase_url!r}, supabase_publishable_key=***, "
            f"model_metadata={self.model_metadata!r}, model_artifact={self.model_artifact!r}, "
            f"http_host={self.http_host!r}, http_port={self.http_port!r}, "
            f"http_timeout_seconds={self.http_timeout_seconds!r})"
        )
