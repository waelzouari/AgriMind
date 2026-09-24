"""Dependency-light color-centroid baseline for model comparison."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from agrimind_cv.contracts import CanonicalLabel, Sample
from agrimind_cv.metrics import MetricsReport, classification_metrics
from agrimind_cv.split import SplitResult


def _mean_rgb(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        pixels = np.asarray(image.convert("RGB").resize((32, 32)), dtype=np.float32)
    result: np.ndarray = pixels.mean(axis=(0, 1)) / 255.0
    return result


def evaluate_mean_rgb_centroid_baseline(
    dataset_root: Path, samples: tuple[Sample, ...], split: SplitResult
) -> MetricsReport:
    """Fit class mean-RGB centroids on train and score validation only."""
    labels = (CanonicalLabel.NORMAL.value, CanonicalLabel.ANOMALY.value)
    features = {
        sample.relative_path: _mean_rgb(sample.resolved_path(dataset_root)) for sample in samples
    }
    centroids: dict[str, np.ndarray] = {}
    for label in labels:
        rows = [
            features[sample.relative_path]
            for sample in samples
            if split.assignments[sample.relative_path] == "train"
            and sample.canonical_label.value == label
        ]
        if not rows:
            raise ValueError(f"training partition has no {label} samples")
        centroids[label] = np.mean(rows, axis=0)
    actual: list[str] = []
    predicted: list[str] = []
    for sample in samples:
        if split.assignments[sample.relative_path] != "validation":
            continue
        actual.append(sample.canonical_label.value)
        predicted.append(
            min(
                labels,
                key=lambda label: float(
                    np.linalg.norm(features[sample.relative_path] - centroids[label])
                ),
            )
        )
    return classification_metrics(actual, predicted, labels)
