"""Dataset provenance validation and file fingerprints."""

from __future__ import annotations

import hashlib
from pathlib import Path

from agrimind_cv.config import DatasetConfig


class ProvenanceError(ValueError):
    pass


APPROVED_LICENSES = frozenset({"CC-BY-4.0", "CC0-1.0"})


def validate_provenance(config: DatasetConfig) -> None:
    if not config.source_url.startswith("https://") or not config.doi.startswith("10."):
        raise ProvenanceError("authoritative HTTPS source and DOI are required")
    if config.license_id not in APPROVED_LICENSES:
        raise ProvenanceError(f"license is not approved for training: {config.license_id}")
    if len(config.source_revision) != 40 or any(
        character not in "0123456789abcdef" for character in config.source_revision
    ):
        raise ProvenanceError("source revision must be a pinned 40-character Git commit")
    if config.archive_sha256 is not None and (
        len(config.archive_sha256) != 64
        or any(character not in "0123456789abcdef" for character in config.archive_sha256)
    ):
        raise ProvenanceError("archive SHA-256 must be lowercase hexadecimal when supplied")


def file_digest(path: Path, algorithm: str = "sha256") -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
