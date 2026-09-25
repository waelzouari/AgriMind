"""Dataset source verification and file fingerprints."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from agrimind_cv.config import DatasetConfig
from agrimind_cv.contracts import SourceEvidence, SourceVerificationStatus


class ProvenanceError(ValueError):
    pass


def file_digest(path: Path, algorithm: str = "sha256") -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_provenance(config: DatasetConfig) -> None:
    if not config.source_url.startswith("https://"):
        raise ProvenanceError("an HTTPS retrieval source is required")
    if len(config.source_revision) != 40 or any(
        character not in "0123456789abcdef" for character in config.source_revision
    ):
        raise ProvenanceError("source revision must be a lowercase 40-character Git commit")
    if config.archive_sha256 is not None and (
        len(config.archive_sha256) != 64
        or any(character not in "0123456789abcdef" for character in config.archive_sha256)
    ):
        raise ProvenanceError("archive SHA-256 must be lowercase hexadecimal")


def verify_source(
    root: Path,
    config: DatasetConfig,
    *,
    archive: Path | None = None,
    evidence_file: Path | None = None,
) -> SourceEvidence:
    """Return evidence without ever upgrading an unverifiable source."""
    validate_provenance(config)
    if (root / ".git").exists():
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
            remote = subprocess.run(
                ["git", "-C", str(root), "remote", "get-url", "origin"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            dirty = bool(
                subprocess.run(
                    ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=all"],
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout.strip()
            )
        except (OSError, subprocess.CalledProcessError) as error:
            raise ProvenanceError("Git source metadata exists but cannot be verified") from error
        verified = (
            revision == config.source_revision
            and remote.removesuffix(".git").lower()
            == config.source_url.removesuffix(".git").lower()
            and not dirty
        )
        return SourceEvidence(
            1,
            SourceVerificationStatus.VERIFIED if verified else SourceVerificationStatus.UNVERIFIED,
            "git_checkout",
            config.source_url,
            config.source_revision,
            revision,
            None,
            None,
            (
                "Git revision and origin match and checkout is clean"
                if verified
                else "Git revision/origin mismatch or checkout contains modifications"
            ),
        )
    if archive is not None:
        if not archive.is_file() or config.archive_sha256 is None:
            raise ProvenanceError("archive verification requires an existing archive and checksum")
        observed = file_digest(archive)
        verified = observed == config.archive_sha256
        return SourceEvidence(
            1,
            SourceVerificationStatus.VERIFIED if verified else SourceVerificationStatus.UNVERIFIED,
            "archive_sha256",
            config.source_url,
            config.source_revision,
            None,
            observed,
            archive.as_posix(),
            "Archive checksum matches" if verified else "Archive checksum mismatch",
        )
    if evidence_file is not None:
        try:
            raw = json.loads(evidence_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ProvenanceError("source evidence record is unreadable") from error
        exact = {
            "schema_version": 1,
            "source_url": config.source_url,
            "source_revision": config.source_revision,
            "archive_sha256": config.archive_sha256,
        }
        verified = raw == exact
        return SourceEvidence(
            1,
            SourceVerificationStatus.VERIFIED if verified else SourceVerificationStatus.UNVERIFIED,
            "versioned_record",
            config.source_url,
            config.source_revision,
            None,
            config.archive_sha256,
            evidence_file.as_posix(),
            "Evidence record matches configuration" if verified else "Evidence record mismatch",
        )
    return SourceEvidence(
        1,
        SourceVerificationStatus.UNVERIFIED,
        "none",
        config.source_url,
        config.source_revision,
        None,
        None,
        None,
        "No Git, archive, or versioned acquisition evidence was supplied",
    )
