import json
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from agrimind_cv.config import DatasetConfig
from agrimind_cv.contracts import SourceVerificationStatus
from agrimind_cv.provenance import ProvenanceError, file_digest, validate_provenance, verify_source


def test_provenance_contract_and_no_evidence_is_unverified(
    tmp_path: Path, dataset_config_file: Path
) -> None:
    config = DatasetConfig.load(dataset_config_file)
    validate_provenance(config)
    root = tmp_path / "dataset"
    root.mkdir()
    result = verify_source(root, config)
    assert result.status == SourceVerificationStatus.UNVERIFIED


def test_matching_versioned_evidence_is_verified(tmp_path: Path, dataset_config_file: Path) -> None:
    config = DatasetConfig.load(dataset_config_file)
    root = tmp_path / "dataset"
    root.mkdir()
    evidence = tmp_path / "source-evidence.json"
    evidence.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source_url": config.source_url,
                "source_revision": config.source_revision,
                "archive_sha256": config.archive_sha256,
            }
        ),
        encoding="utf-8",
    )
    assert (
        verify_source(root, config, evidence_file=evidence).status
        == SourceVerificationStatus.VERIFIED
    )
    evidence.write_text("{}", encoding="utf-8")
    assert (
        verify_source(root, config, evidence_file=evidence).status
        == SourceVerificationStatus.UNVERIFIED
    )


def test_archive_checksum_match_and_mismatch(tmp_path: Path, dataset_config_file: Path) -> None:
    config = DatasetConfig.load(dataset_config_file)
    root = tmp_path / "dataset"
    root.mkdir()
    archive = tmp_path / "dataset.zip"
    archive.write_bytes(b"immutable")
    verified = replace(config, archive_sha256=file_digest(archive))
    assert (
        verify_source(root, verified, archive=archive).status == SourceVerificationStatus.VERIFIED
    )
    assert (
        verify_source(root, config, archive=archive).status == SourceVerificationStatus.UNVERIFIED
    )


def test_invalid_revision_or_archive_checksum_fails(dataset_config_file: Path) -> None:
    config = DatasetConfig.load(dataset_config_file)
    with pytest.raises(ProvenanceError, match="revision"):
        validate_provenance(replace(config, source_revision="abc"))
    with pytest.raises(ProvenanceError, match="SHA-256"):
        validate_provenance(replace(config, archive_sha256="unknown"))


def test_git_checkout_must_match_origin_revision_and_be_clean(
    tmp_path: Path, dataset_config_file: Path
) -> None:
    root = tmp_path / "checkout"
    root.mkdir()
    subprocess.run(["git", "init", str(root)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "test@example.invalid"], check=True
    )
    subprocess.run(["git", "-C", str(root), "config", "user.name", "AGM-030 test"], check=True)
    source_url = "https://example.test/dataset"
    subprocess.run(["git", "-C", str(root), "remote", "add", "origin", source_url], check=True)
    sample = root / "sample.txt"
    sample.write_text("verified", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "sample.txt"], check=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-m", "fixture"], check=True, capture_output=True
    )
    revision = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    config = replace(
        DatasetConfig.load(dataset_config_file),
        source_url=source_url,
        source_revision=revision,
    )
    assert verify_source(root, config).status == SourceVerificationStatus.VERIFIED
    sample.write_text("modified", encoding="utf-8")
    assert verify_source(root, config).status == SourceVerificationStatus.UNVERIFIED
