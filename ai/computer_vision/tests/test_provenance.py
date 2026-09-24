from dataclasses import replace
from pathlib import Path

import pytest

from agrimind_cv.config import DatasetConfig
from agrimind_cv.provenance import ProvenanceError, validate_provenance


def test_verified_provenance_is_accepted(dataset_config_file: Path) -> None:
    validate_provenance(DatasetConfig.load(dataset_config_file))


def test_missing_or_unapproved_license_blocks_dataset(dataset_config_file: Path) -> None:
    config = DatasetConfig.load(dataset_config_file)
    with pytest.raises(ProvenanceError, match="not approved"):
        validate_provenance(replace(config, license_id="NOT-VERIFIED"))


def test_invalid_archive_checksum_blocks_dataset(dataset_config_file: Path) -> None:
    config = DatasetConfig.load(dataset_config_file)
    with pytest.raises(ProvenanceError, match="SHA-256"):
        validate_provenance(replace(config, archive_sha256="unknown"))
