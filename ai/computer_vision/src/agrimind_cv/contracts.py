"""Stable dataset and artifact contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class CanonicalLabel(StrEnum):
    NORMAL = "NORMAL"
    ANOMALY = "ANOMALY"


class AuditStatus(StrEnum):
    VALID = "valid"
    INVALID = "invalid"
    SUSPICIOUS = "suspicious"


@dataclass(frozen=True, slots=True)
class Sample:
    relative_path: str
    source_label: str
    canonical_label: CanonicalLabel
    sha256: str
    perceptual_hash: str
    width: int
    height: int
    channels: int
    group_id: str | None = None

    def resolved_path(self, root: Path) -> Path:
        path = (root / self.relative_path).resolve()
        if root.resolve() not in path.parents:
            raise ValueError("sample path escapes dataset root")
        return path
