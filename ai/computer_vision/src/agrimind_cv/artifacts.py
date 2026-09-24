"""Atomic, traceable artifact metadata."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


class ArtifactError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ArtifactMetadata:
    schema_version: int
    artifact_id: str
    created_at: str
    code_revision: str
    dataset_id: str
    dataset_version: str
    dataset_fingerprint: str
    split_fingerprint: str
    training_config: dict[str, Any]
    architecture: str
    pretrained_weights: str | None
    preprocessing: dict[str, Any]
    label_mapping: dict[str, int]
    metrics: dict[str, Any]

    def validate(self) -> None:
        if self.schema_version != 1 or not self.artifact_id or not self.code_revision:
            raise ArtifactError("artifact identity, schema version, and code revision are required")
        try:
            parsed = datetime.fromisoformat(self.created_at.replace("Z", "+00:00"))
        except ValueError as error:
            raise ArtifactError("created_at must be RFC 3339") from error
        if parsed.utcoffset() is None or not self.dataset_fingerprint or not self.split_fingerprint:
            raise ArtifactError("UTC timestamp and dataset/split fingerprints are required")
        if self.label_mapping != {"NORMAL": 0, "ANOMALY": 1}:
            raise ArtifactError("artifact must contain the binary AgriMind label mapping")


def write_metadata(metadata: ArtifactMetadata, destination: Path) -> None:
    metadata.validate()
    if destination.exists():
        raise ArtifactError("artifact metadata already exists; refusing to overwrite")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    try:
        temporary.write_text(
            json.dumps(asdict(metadata), indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
