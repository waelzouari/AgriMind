"""Versioned computer-vision data contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

LABEL_MAP_VERSION = "agrimind-cv-binary-label-map-v1"
RELATED_MANIFEST_VERSION = "agrimind-cv-related-manifest-v1"
SPLIT_CONTRACT_VERSION = "agrimind-cv-group-split-v1"


class CanonicalLabel(StrEnum):
    NORMAL = "NORMAL"
    ANOMALY = "ANOMALY"


class SourceVerificationStatus(StrEnum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"


class Partition(StrEnum):
    TRAIN = "TRAIN"
    VALIDATION = "VALIDATION"
    TEST = "TEST"


@dataclass(frozen=True, slots=True)
class SourceEvidence:
    schema_version: int
    status: SourceVerificationStatus
    method: str
    source_url: str
    source_revision: str
    observed_revision: str | None
    archive_sha256: str | None
    evidence_path: str | None
    detail: str


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
    related_group_id: str = ""
    quarantined: bool = False
    quarantine_reason: str | None = None

    def resolved_path(self, root: Path) -> Path:
        path = (root / self.relative_path).resolve()
        if root.resolve() not in path.parents:
            raise ValueError("sample path escapes dataset root")
        return path
