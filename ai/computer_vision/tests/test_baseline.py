from pathlib import Path

from conftest import make_image

from agrimind_cv.baseline import evaluate_mean_rgb_centroid_baseline
from agrimind_cv.contracts import CanonicalLabel, Partition, Sample
from agrimind_cv.split import SplitResult


def test_mean_rgb_baseline_fits_train_and_scores_validation_only(tmp_path: Path) -> None:
    samples = []
    assignments = {}
    for name, label, color, partition in (
        ("normal-train.png", CanonicalLabel.NORMAL, (0, 180, 0), "train"),
        ("anomaly-train.png", CanonicalLabel.ANOMALY, (180, 0, 0), "train"),
        ("normal-val.png", CanonicalLabel.NORMAL, (0, 170, 0), "validation"),
        ("anomaly-val.png", CanonicalLabel.ANOMALY, (170, 0, 0), "validation"),
    ):
        make_image(tmp_path / name, color)
        samples.append(Sample(name, name, label, name, "0" * 16, 12, 10, 3, name))
        assignments[name] = Partition(partition.upper())
    split = SplitResult(assignments, {}, {}, {}, "a" * 64)
    report = evaluate_mean_rgb_centroid_baseline(tmp_path, tuple(samples), split)
    assert report.accuracy == 1.0
    assert evaluate_mean_rgb_centroid_baseline(tmp_path, tuple(reversed(samples)), split) == report


def test_baseline_never_opens_test_images(tmp_path: Path) -> None:
    samples = []
    assignments = {}
    for name, label, color, partition in (
        ("normal-train.png", CanonicalLabel.NORMAL, (0, 180, 0), Partition.TRAIN),
        ("anomaly-train.png", CanonicalLabel.ANOMALY, (180, 0, 0), Partition.TRAIN),
        ("normal-val.png", CanonicalLabel.NORMAL, (0, 170, 0), Partition.VALIDATION),
        ("anomaly-val.png", CanonicalLabel.ANOMALY, (170, 0, 0), Partition.VALIDATION),
        ("missing-test.png", CanonicalLabel.NORMAL, (0, 0, 0), Partition.TEST),
    ):
        if partition != Partition.TEST:
            make_image(tmp_path / name, color)
        samples.append(Sample(name, name, label, name, "0" * 16, 12, 10, 3, name))
        assignments[name] = partition
    split = SplitResult(assignments, {}, {}, {}, "a" * 64)
    assert evaluate_mean_rgb_centroid_baseline(tmp_path, tuple(samples), split).accuracy == 1.0
