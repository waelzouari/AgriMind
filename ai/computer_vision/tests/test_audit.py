from dataclasses import replace
from pathlib import Path

from conftest import make_image

from agrimind_cv.audit import audit_dataset, write_related_manifest
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
    assert first.dataset_fingerprint == second.dataset_fingerprint
    assert first.related_manifest_fingerprint == second.related_manifest_fingerprint
    assert first.valid_for_manifest
    manifest = tmp_path / "manifest.csv"
    write_related_manifest(first, manifest)
    rows = manifest.read_text(encoding="utf-8").splitlines()
    assert len(rows) == 2
    assert "binary_label" in rows[0]
    assert any("ANOMALY" in row for row in rows)


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


def test_same_label_near_duplicates_form_a_transitive_related_group(
    tmp_path: Path, dataset_config_file: Path
) -> None:
    root = tmp_path / "images"
    make_image(root / "healthy" / "a.png", (10, 20, 30))
    raw = (root / "healthy" / "a.png").read_bytes()
    (root / "healthy" / "b.png").write_bytes(raw + b"one")
    (root / "healthy" / "c.png").write_bytes(raw + b"two")
    make_image(root / "anomaly" / "different.png", (200, 150, 30))
    report = audit_dataset(root, DatasetConfig.load(dataset_config_file))
    groups = {
        sample.related_group_id
        for sample in report.samples
        if sample.relative_path.startswith("healthy/")
    }
    assert len(groups) == 1
    assert len(report.near_duplicate_candidates) >= 2


def test_cross_label_near_duplicates_quarantine_all_involved_samples(
    tmp_path: Path, dataset_config_file: Path
) -> None:
    root = tmp_path / "images"
    make_image(root / "healthy" / "a.png", (10, 20, 30))
    raw = (root / "healthy" / "a.png").read_bytes()
    (root / "anomaly").mkdir()
    (root / "anomaly" / "b.png").write_bytes(raw + b"different bytes")
    report = audit_dataset(root, DatasetConfig.load(dataset_config_file))
    assert len(report.cross_label_candidates) == 1
    assert report.quarantined_count == 2
    assert not report.eligible_samples
    assert all(
        sample.quarantine_reason == "cross_label_near_duplicate_candidate"
        for sample in report.samples
    )


def test_dataset_fingerprint_is_order_invariant_and_content_sensitive(
    tmp_path: Path, dataset_config_file: Path
) -> None:
    config = DatasetConfig.load(dataset_config_file)
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    for root, order in ((first_root, ("a", "b")), (second_root, ("b", "a"))):
        colors = {"a": (10, 20, 30), "b": (200, 150, 30)}
        labels = {"a": "healthy", "b": "anomaly"}
        for name in order:
            make_image(root / labels[name] / f"{name}.png", colors[name])
    first = audit_dataset(first_root, config)
    second = audit_dataset(second_root, config)
    assert first.dataset_fingerprint == second.dataset_fingerprint
    make_image(second_root / "anomaly" / "b.png", (210, 150, 30))
    assert audit_dataset(second_root, config).dataset_fingerprint != first.dataset_fingerprint


def test_threshold_configuration_controls_candidate_detection(
    tmp_path: Path, dataset_config_file: Path
) -> None:
    root = tmp_path / "images"
    make_image(root / "healthy" / "a.png", (10, 20, 30))
    raw = (root / "healthy" / "a.png").read_bytes()
    (root / "healthy" / "b.png").write_bytes(raw + b"different")
    config = replace(DatasetConfig.load(dataset_config_file), near_duplicate_hamming_threshold=0)
    assert audit_dataset(root, config).near_duplicate_candidates == (
        ("healthy/a.png", "healthy/b.png"),
    )
