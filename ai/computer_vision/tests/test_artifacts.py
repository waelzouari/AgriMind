from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from agrimind_cv.artifacts import (
    ArtifactError,
    ArtifactMetadata,
    read_metadata,
    write_metadata,
)
from agrimind_cv.provenance import file_digest

SCHEMA = Path(__file__).parents[1] / "data_contracts/artifact-metadata.v2.schema.json"


def metadata(model: Path) -> ArtifactMetadata:
    return ArtifactMetadata(
        2,
        "cv-test-1",
        "1.0.0",
        datetime(2026, 9, 23, tzinfo=UTC).isoformat().replace("+00:00", "Z"),
        "a" * 40,
        True,
        {
            "format": "pytorch_state_dict",
            "path": "ai/computer_vision/artifacts/test.pt",
            "size_bytes": model.stat().st_size,
            "sha256": file_digest(model),
        },
        "mobilenet_v2",
        "mobilenet_v2",
        "IMAGENET1K_V1",
        "agrimind-cv-binary-label-map-v1",
        {"NORMAL": 0, "ANOMALY": 1},
        "agrimind-cv-mobilenet-v2-preprocessing-v1",
        {
            "id": "test",
            "version": "1",
            "fingerprint": "b" * 64,
            "config_sha256": "c" * 64,
            "source_verification": "VERIFIED",
            "source_evidence": {
                "schema_version": 1,
                "status": "VERIFIED",
                "method": "archive_sha256",
                "source_url": "https://example.test/dataset",
                "source_revision": "1" * 40,
                "observed_revision": None,
                "archive_sha256": "2" * 64,
                "evidence_path": "data/source.zip",
                "detail": "Archive checksum matches",
            },
        },
        "d" * 64,
        {
            "contract_version": "agrimind-cv-group-split-v1",
            "fingerprint": "e" * 64,
            "seed": 42,
            "ratios": {"train": 0.7, "validation": 0.15, "test": 0.15},
            "counts": {"TRAIN": 70, "VALIDATION": 15, "TEST": 15},
            "class_counts": {
                partition: {"NORMAL": count // 2, "ANOMALY": count - count // 2}
                for partition, count in {"TRAIN": 70, "VALIDATION": 15, "TEST": 15}.items()
            },
        },
        {
            "config_version": "agrimind-cv-mobilenet-v2-training-v1",
            "config_sha256": "f" * 64,
            "random_seed": 42,
            "resolved_config": {"epochs": 10},
            "outcome": {
                "epochs_executed": 4,
                "best_epoch": 2,
                "stopped_early": True,
                "class_weights": [1.0, 1.0],
                "duration_seconds": 12.5,
            },
        },
        {
            "python": "3.11.10",
            "numpy": "2.1.3",
            "pillow": "11.0.0",
            "torch": "2.5.1",
            "torchvision": "0.20.1",
            "platform": "test",
            "device": "cpu",
            "cuda": None,
            "cudnn": None,
            "deterministic_settings": {"workers": 0},
        },
        {
            "baseline_validation": {},
            "candidate_validation": {},
            "selection_rule_version": "agrimind-cv-validation-selection-v1",
            "selection_reason": "candidate wins",
            "test_evaluated": False,
            "threshold_selection": "DEFERRED_TO_AGM_031",
        },
    )


def test_metadata_is_schema_valid_atomic_and_readable(tmp_path: Path) -> None:
    model = tmp_path / "model.pt"
    model.write_bytes(b"model")
    destination = tmp_path / "metadata.json"
    write_metadata(metadata(model), destination, schema_path=SCHEMA, model_path=model)
    assert read_metadata(destination, schema_path=SCHEMA, model_path=model) == metadata(model)
    with pytest.raises(ArtifactError, match="overwrite"):
        write_metadata(metadata(model), destination, schema_path=SCHEMA, model_path=model)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"code_revision": "abc123"}, "does not match"),
        ({"artifact_version": "v1"}, "does not match"),
        ({"created_at": "yesterday"}, "date-time"),
        ({"label_map_version": "missing"}, "binary-label-map"),
        ({"preprocessing_contract_version": "missing"}, "preprocessing"),
    ],
)
def test_invalid_metadata_fails_schema(
    tmp_path: Path, change: dict[str, object], message: str
) -> None:
    model = tmp_path / "model.pt"
    model.write_bytes(b"model")
    with pytest.raises(ArtifactError, match=message):
        write_metadata(
            replace(metadata(model), **change),
            tmp_path / "m.json",
            schema_path=SCHEMA,
            model_path=model,
        )


def test_test_evaluated_must_be_false(tmp_path: Path) -> None:
    model = tmp_path / "model.pt"
    model.write_bytes(b"model")
    value = metadata(model)
    evaluation = {**value.evaluation, "test_evaluated": True}
    with pytest.raises(ArtifactError, match="False"):
        write_metadata(
            replace(value, evaluation=evaluation),
            tmp_path / "m.json",
            schema_path=SCHEMA,
            model_path=model,
        )


def test_split_counts_and_training_outcome_must_be_consistent(tmp_path: Path) -> None:
    model = tmp_path / "model.pt"
    model.write_bytes(b"model")
    value = metadata(model)
    bad_split = {**value.split, "counts": {"TRAIN": 71, "VALIDATION": 15, "TEST": 15}}
    with pytest.raises(ArtifactError, match="split counts"):
        write_metadata(
            replace(value, split=bad_split),
            tmp_path / "split.json",
            schema_path=SCHEMA,
            model_path=model,
        )
    bad_outcome = {**value.training["outcome"], "best_epoch": 5}
    with pytest.raises(ArtifactError, match="training outcome"):
        write_metadata(
            replace(value, training={**value.training, "outcome": bad_outcome}),
            tmp_path / "training.json",
            schema_path=SCHEMA,
            model_path=model,
        )


def test_model_size_and_checksum_mismatches_fail(tmp_path: Path) -> None:
    model = tmp_path / "model.pt"
    model.write_bytes(b"model")
    value = metadata(model)
    with pytest.raises(ArtifactError, match="size mismatch"):
        write_metadata(
            replace(value, artifact={**value.artifact, "size_bytes": 99}),
            tmp_path / "a.json",
            schema_path=SCHEMA,
            model_path=model,
        )
    with pytest.raises(ArtifactError, match="checksum mismatch"):
        write_metadata(
            replace(value, artifact={**value.artifact, "sha256": "0" * 64}),
            tmp_path / "b.json",
            schema_path=SCHEMA,
            model_path=model,
        )


def test_failed_publication_leaves_no_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = tmp_path / "model.pt"
    model.write_bytes(b"model")
    destination = tmp_path / "metadata.json"
    monkeypatch.setattr(
        "agrimind_cv.artifacts.os.replace", lambda *_: (_ for _ in ()).throw(OSError("stop"))
    )
    with pytest.raises(OSError):
        write_metadata(
            metadata(model),
            destination,
            schema_path=SCHEMA,
            model_path=model,
            cleanup_model_on_failure=True,
        )
    assert not destination.exists()
    assert not destination.with_suffix(".json.tmp").exists()
    assert not model.exists()


def test_schema_failure_rolls_back_official_model(tmp_path: Path) -> None:
    model = tmp_path / "model.pt"
    model.write_bytes(b"model")
    invalid = replace(metadata(model), code_revision="not-a-revision")
    with pytest.raises(ArtifactError, match="does not match"):
        write_metadata(
            invalid,
            tmp_path / "metadata.json",
            schema_path=SCHEMA,
            model_path=model,
            cleanup_model_on_failure=True,
        )
    assert not model.exists()
