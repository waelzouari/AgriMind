"""Dependency-light color-centroid baseline for model comparison."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from agrimind_cv.contracts import CanonicalLabel, Partition, Sample
from agrimind_cv.metrics import MetricsReport, classification_metrics
from agrimind_cv.split import SplitResult

BASELINE_PREPROCESSING_VERSION = "agrimind-cv-mean-rgb-32-v1"


@dataclass(frozen=True, slots=True)
class BaselineOutcome:
    metrics: MetricsReport
    centroids: dict[str, tuple[float, float, float]]


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
    selected = tuple(
        sample
        for sample in samples
        if split.assignments[sample.relative_path] in {Partition.TRAIN, Partition.VALIDATION}
    )
    features = {
        sample.relative_path: _mean_rgb(sample.resolved_path(dataset_root)) for sample in selected
    }
    centroids: dict[str, np.ndarray] = {}
    for label in labels:
        rows = [
            features[sample.relative_path]
            for sample in selected
            if split.assignments[sample.relative_path] == Partition.TRAIN
            and sample.canonical_label.value == label
        ]
        if not rows:
            raise ValueError(f"training partition has no {label} samples")
        centroids[label] = np.mean(rows, axis=0)
    actual: list[str] = []
    predicted: list[str] = []
    for sample in selected:
        if split.assignments[sample.relative_path] != Partition.VALIDATION:
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


def train_mean_rgb_centroid_baseline(
    dataset_root: Path, samples: tuple[Sample, ...], split: SplitResult
) -> BaselineOutcome:
    labels = (CanonicalLabel.NORMAL.value, CanonicalLabel.ANOMALY.value)
    selected = tuple(
        sample
        for sample in samples
        if split.assignments[sample.relative_path] in {Partition.TRAIN, Partition.VALIDATION}
    )
    features = {
        sample.relative_path: _mean_rgb(sample.resolved_path(dataset_root)) for sample in selected
    }
    centroids: dict[str, np.ndarray] = {}
    for label in labels:
        rows = [
            features[sample.relative_path]
            for sample in selected
            if split.assignments[sample.relative_path] == Partition.TRAIN
            and sample.canonical_label.value == label
        ]
        if not rows:
            raise ValueError(f"training partition has no {label} samples")
        centroids[label] = np.mean(rows, axis=0)
    actual: list[str] = []
    predicted: list[str] = []
    for sample in selected:
        if split.assignments[sample.relative_path] != Partition.VALIDATION:
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
    return BaselineOutcome(
        classification_metrics(actual, predicted, labels),
        {
            label: (
                float(centroids[label][0]),
                float(centroids[label][1]),
                float(centroids[label][2]),
            )
            for label in labels
        },
    )


def write_baseline_artifact(outcome: BaselineOutcome, destination: Path) -> None:
    if destination.exists():
        raise FileExistsError("model artifact already exists; refusing to overwrite")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    try:
        temporary.write_text(
            json.dumps(
                {"format": "mean_rgb_centroids_v1", "centroids": outcome.centroids}, sort_keys=True
            )
            + "\n",
            encoding="utf-8",
        )
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
