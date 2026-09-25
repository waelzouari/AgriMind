from __future__ import annotations

import json
from pathlib import Path

import pytest

from agrimind_cv.contracts import CanonicalLabel, Partition, Sample
from agrimind_cv.official_evaluation import (
    OfficialConfig,
    assert_no_content_leakage,
    score_fingerprint,
)
from agrimind_cv.split import SplitResult
from agrimind_cv.training import PartitionScores


def test_official_config_is_strict_and_pins_expected_identities(tmp_path: Path) -> None:
    payload = {
        "schema_version": 1,
        "model_version": "1.0.0",
        "artifact_filename": "model.pt",
        "release_tag": "release-v1",
        "execution_device": "cuda",
        "dataset_fingerprint": "a" * 64,
        "related_manifest_fingerprint": "b" * 64,
        "split_fingerprint": "c" * 64,
        "threshold_rule_version": "agrimind-cv-validation-threshold-v1",
    }
    path = tmp_path / "official.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert OfficialConfig.load(path).model_version == "1.0.0"
    payload["unexpected"] = True
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="fields"):
        OfficialConfig.load(path)


def test_partition_score_fingerprint_is_order_and_value_sensitive() -> None:
    scores = PartitionScores(
        ("a.jpg", "b.jpg"),
        ("healthy", "disease"),
        ("NORMAL", "ANOMALY"),
        (0.25, 0.75),
        1.0,
    )
    first = score_fingerprint(scores, Partition.VALIDATION)
    assert len(first) == 64
    changed = PartitionScores(
        scores.relative_paths,
        scores.source_labels,
        scores.expected,
        (0.25, 0.7500000000000001),
        scores.duration_seconds,
    )
    assert score_fingerprint(changed, Partition.VALIDATION) != first


def test_content_hash_may_not_cross_partitions() -> None:
    samples = (
        Sample("a.jpg", "healthy", CanonicalLabel.NORMAL, "same", "0" * 16, 1, 1, 3, "a"),
        Sample("b.jpg", "healthy", CanonicalLabel.NORMAL, "same", "0" * 16, 1, 1, 3, "b"),
    )
    split = SplitResult(
        {"a.jpg": Partition.TRAIN, "b.jpg": Partition.TEST},
        {"a": Partition.TRAIN, "b": Partition.TEST},
        {},
        {},
        "f" * 64,
    )
    with pytest.raises(ValueError, match="SHA-256"):
        assert_no_content_leakage(samples, split)
