from datetime import UTC, datetime
from pathlib import Path

import pytest

from agrimind_cv.artifacts import ArtifactError, ArtifactMetadata, write_metadata


def metadata() -> ArtifactMetadata:
    return ArtifactMetadata(
        schema_version=1,
        artifact_id="cv-test-1",
        created_at=datetime(2026, 9, 23, tzinfo=UTC).isoformat().replace("+00:00", "Z"),
        code_revision="abc123",
        dataset_id="test",
        dataset_version="1",
        dataset_fingerprint="a" * 64,
        split_fingerprint="b" * 64,
        training_config={"seed": 1},
        architecture="mobilenet_v2",
        pretrained_weights=None,
        preprocessing={"width": 224, "height": 224},
        label_mapping={"NORMAL": 0, "ANOMALY": 1},
        metrics={"accuracy": 0.5},
    )


def test_metadata_is_atomic_and_never_silently_overwritten(tmp_path: Path) -> None:
    destination = tmp_path / "artifact" / "metadata.json"
    write_metadata(metadata(), destination)
    assert destination.exists()
    with pytest.raises(ArtifactError, match="overwrite"):
        write_metadata(metadata(), destination)
