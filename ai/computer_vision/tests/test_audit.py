from pathlib import Path

from conftest import make_image

from agrimind_cv.audit import audit_dataset, write_manifest_csv
from agrimind_cv.config import DatasetConfig


def test_valid_tiny_dataset_has_deterministic_counts_and_fingerprint(
    tmp_path: Path, dataset_config_file: Path
) -> None:
    root = tmp_path / "images"
    make_image(root / "healthy" / "a.png", (0, 180, 0))
    make_image(root / "anomaly" / "b.png", (180, 0, 0))
    config = DatasetConfig.load(dataset_config_file)
    first = audit_dataset(root, config)
    second = audit_dataset(root, config)
    assert first.class_counts == {"ANOMALY": 1, "NORMAL": 1}
    assert first.fingerprint == second.fingerprint
    assert first.valid_for_manifest
    manifest = tmp_path / "manifest.csv"
    write_manifest_csv(first, manifest)
    rows = manifest.read_text(encoding="utf-8").splitlines()
    assert len(rows) == 3
    assert "canonical_label" in rows[0]
    assert any("ANOMALY" in row for row in rows[1:])


def test_unreadable_unknown_and_unsupported_samples_are_reported(
    tmp_path: Path, dataset_config_file: Path
) -> None:
    root = tmp_path / "images"
    (root / "healthy").mkdir(parents=True)
    (root / "healthy" / "broken.png").write_text("not an image", encoding="utf-8")
    make_image(root / "unknown" / "sample.png", (1, 2, 3))
    (root / "healthy" / "notes.txt").write_text("metadata", encoding="utf-8")
    report = audit_dataset(root, DatasetConfig.load(dataset_config_file))
    assert {problem.code for problem in report.problems} == {
        "unreadable_image",
        "unknown_label",
        "unsupported_extension",
    }
    assert not report.valid_for_manifest


def test_exact_duplicate_and_conflicting_duplicate_are_distinguished(
    tmp_path: Path, dataset_config_file: Path
) -> None:
    root = tmp_path / "images"
    make_image(root / "healthy" / "a.png", (10, 20, 30))
    data = (root / "healthy" / "a.png").read_bytes()
    (root / "healthy" / "copy.png").write_bytes(data)
    (root / "anomaly").mkdir()
    (root / "anomaly" / "conflict.png").write_bytes(data)
    report = audit_dataset(root, DatasetConfig.load(dataset_config_file))
    codes = {problem.code for problem in report.problems}
    assert "duplicate_conflict" in codes
    assert not report.valid_for_manifest


def test_explicitly_excluded_source_is_reported_but_not_manifested(
    tmp_path: Path, dataset_config_file: Path
) -> None:
    from dataclasses import replace

    root = tmp_path / "images"
    make_image(root / "healthy" / "ok.png", (0, 180, 0))
    make_image(root / "rejected" / "bad.png", (1, 2, 3))
    config = replace(
        DatasetConfig.load(dataset_config_file), excluded_source_labels=frozenset({"rejected"})
    )
    report = audit_dataset(root, config)
    assert [problem.code for problem in report.problems] == ["excluded_source_label"]
    assert len(report.samples) == 1
    assert report.valid_for_manifest
