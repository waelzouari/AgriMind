"""Validated, atomic publication of lightweight artifact metadata."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


class ArtifactError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class GitState:
    revision: str
    dirty: bool


@dataclass(frozen=True, slots=True)
class ArtifactMetadata:
    schema_version: int
    artifact_id: str
    artifact_version: str
    created_at: str
    code_revision: str
    git_dirty: bool
    artifact: dict[str, Any]
    selected_model: str
    architecture: str
    pretrained_weights: str | None
    label_map_version: str
    label_mapping: dict[str, int]
    preprocessing_contract_version: str
    dataset: dict[str, Any]
    related_manifest_fingerprint: str
    split: dict[str, Any]
    training: dict[str, Any]
    runtime: dict[str, Any]
    evaluation: dict[str, Any]


def repository_git_state(root: Path) -> GitState:
    try:
        revision = (
            subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            )
            .stdout.strip()
            .lower()
        )
        dirty = bool(
            subprocess.run(
                ["git", "-C", str(root), "status", "--porcelain"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise ArtifactError("official training requires an identifiable Git checkout") from error
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ArtifactError("Git revision must be a full 40-character SHA-1")
    return GitState(revision, dirty)


def _schema(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ArtifactError("artifact metadata schema is unreadable") from error
    if not isinstance(value, dict):
        raise ArtifactError("artifact metadata schema must be an object")
    return value


def validate_metadata(metadata: ArtifactMetadata, schema_path: Path) -> None:
    payload = asdict(metadata)
    errors = sorted(
        Draft202012Validator(_schema(schema_path), format_checker=FormatChecker()).iter_errors(
            payload
        ),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        raise ArtifactError(
            "invalid artifact metadata: " + "; ".join(error.message for error in errors)
        )
    try:
        parsed = datetime.fromisoformat(metadata.created_at.replace("Z", "+00:00"))
    except ValueError as error:
        raise ArtifactError("created_at must be an RFC 3339 timestamp") from error
    if parsed.utcoffset() is None or not metadata.created_at.endswith("Z"):
        raise ArtifactError("created_at must be UTC")
    if metadata.label_mapping != {"NORMAL": 0, "ANOMALY": 1}:
        raise ArtifactError("artifact label mapping must be exactly NORMAL=0, ANOMALY=1")
    if metadata.evaluation.get("test_evaluated") is not False:
        raise ArtifactError("AGM-030 metadata must state test_evaluated=false")
    source_evidence = metadata.dataset.get("source_evidence")
    if not isinstance(source_evidence, dict) or source_evidence.get(
        "status"
    ) != metadata.dataset.get("source_verification"):
        raise ArtifactError("dataset source evidence must match source verification")
    counts = metadata.split.get("counts")
    class_counts = metadata.split.get("class_counts")
    if (
        not isinstance(counts, dict)
        or not isinstance(class_counts, dict)
        or any(
            counts.get(partition) != sum(class_counts.get(partition, {}).values())
            for partition in ("TRAIN", "VALIDATION", "TEST")
        )
    ):
        raise ArtifactError("split counts must match per-class counts")
    outcome = metadata.training.get("outcome")
    resolved = metadata.training.get("resolved_config")
    if not isinstance(outcome, dict) or not isinstance(resolved, dict):
        raise ArtifactError("training outcome and resolved configuration are required")
    executed = outcome.get("epochs_executed")
    best = outcome.get("best_epoch")
    maximum = resolved.get("epochs")
    stopped_early = outcome.get("stopped_early")
    if (
        not isinstance(executed, int)
        or not isinstance(best, int)
        or not isinstance(maximum, int)
        or not 1 <= best <= executed <= maximum
        or stopped_early is not (executed < maximum)
    ):
        raise ArtifactError("training outcome is inconsistent with configured epochs")


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_metadata(
    metadata: ArtifactMetadata,
    destination: Path,
    *,
    schema_path: Path,
    model_path: Path,
    cleanup_model_on_failure: bool = False,
) -> None:
    """Publish metadata last so no metadata can reference a partial/wrong model."""
    if destination.exists():
        raise ArtifactError("artifact metadata already exists; refusing to overwrite")
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    try:
        if not model_path.is_file():
            raise ArtifactError("model artifact does not exist")
        expected_size = metadata.artifact.get("size_bytes")
        expected_hash = metadata.artifact.get("sha256")
        if expected_size != model_path.stat().st_size:
            raise ArtifactError("model artifact size mismatch")
        if expected_hash != _digest(model_path):
            raise ArtifactError("model artifact checksum mismatch")
        validate_metadata(metadata, schema_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(
            json.dumps(asdict(metadata), indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        if cleanup_model_on_failure:
            model_path.unlink(missing_ok=True)
        raise


def read_metadata(path: Path, *, schema_path: Path, model_path: Path) -> ArtifactMetadata:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        metadata = ArtifactMetadata(**raw)
    except (OSError, json.JSONDecodeError, TypeError) as error:
        raise ArtifactError("artifact metadata is unreadable") from error
    validate_metadata(metadata, schema_path)
    if metadata.artifact.get("size_bytes") != model_path.stat().st_size:
        raise ArtifactError("model artifact size mismatch")
    if metadata.artifact.get("sha256") != _digest(model_path):
        raise ArtifactError("model artifact checksum mismatch")
    return metadata
