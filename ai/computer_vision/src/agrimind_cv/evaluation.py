"""Leakage-resistant binary evaluation and validation-only threshold selection."""

from __future__ import annotations

import math
from dataclasses import dataclass

from agrimind_cv.metrics import MetricsReport, classification_metrics

LABELS = ("NORMAL", "ANOMALY")


@dataclass(frozen=True, slots=True)
class ValidationScores:
    expected: tuple[str, ...]
    anomaly_softmax_probabilities: tuple[float, ...]
    validation_fingerprint: str


@dataclass(frozen=True, slots=True)
class HeldOutTestScores:
    expected: tuple[str, ...]
    anomaly_softmax_probabilities: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class ThresholdSelection:
    threshold: float
    rule_version: str
    validation_fingerprint: str
    metrics: MetricsReport


@dataclass(frozen=True, slots=True)
class FrozenEvaluationEvidence:
    artifact_sha256: str
    model_version: str
    preprocessing_version: str
    threshold: ThresholdSelection
    model_frozen: bool = True
    preprocessing_frozen: bool = True
    threshold_frozen: bool = True


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    metrics: MetricsReport
    roc_auc: float
    average_precision: float
    sample_count: int


def _validated(expected: tuple[str, ...], scores: tuple[float, ...]) -> None:
    if not expected or len(expected) != len(scores):
        raise ValueError("labels and scores must be non-empty and equal length")
    if any(label not in LABELS for label in expected):
        raise ValueError("labels must be NORMAL or ANOMALY")
    if any(not math.isfinite(score) or not 0.0 <= score <= 1.0 for score in scores):
        raise ValueError("anomaly softmax probabilities must be finite values in [0, 1]")


def _predictions(scores: tuple[float, ...], threshold: float) -> list[str]:
    if not math.isfinite(threshold) or not 0.0 <= threshold <= 1.0:
        raise ValueError("threshold must be a finite value in [0, 1]")
    return ["ANOMALY" if score >= threshold else "NORMAL" for score in scores]


def metrics_at_threshold(
    expected: tuple[str, ...], scores: tuple[float, ...], threshold: float
) -> MetricsReport:
    _validated(expected, scores)
    return classification_metrics(list(expected), _predictions(scores, threshold), LABELS)


def roc_auc(expected: tuple[str, ...], scores: tuple[float, ...]) -> float:
    """Return tie-aware ROC-AUC using average ranks."""
    _validated(expected, scores)
    positives = sum(label == "ANOMALY" for label in expected)
    negatives = len(expected) - positives
    if positives == 0 or negatives == 0:
        raise ValueError("ROC-AUC requires both classes")
    ranked = sorted(zip(scores, expected, strict=True), key=lambda item: item[0])
    positive_rank_sum = 0.0
    index = 0
    while index < len(ranked):
        end = index + 1
        while end < len(ranked) and ranked[end][0] == ranked[index][0]:
            end += 1
        average_rank = ((index + 1) + end) / 2
        positive_rank_sum += average_rank * sum(
            label == "ANOMALY" for _, label in ranked[index:end]
        )
        index = end
    return (positive_rank_sum - positives * (positives + 1) / 2) / (positives * negatives)


def average_precision(expected: tuple[str, ...], scores: tuple[float, ...]) -> float:
    """Return tie-aware non-interpolated average precision for ANOMALY."""
    _validated(expected, scores)
    positives = sum(label == "ANOMALY" for label in expected)
    if positives == 0:
        raise ValueError("average precision requires a positive class")
    ranked = sorted(zip(scores, expected, strict=True), key=lambda item: item[0], reverse=True)
    true_positive = 0
    seen = 0
    previous_recall = 0.0
    result = 0.0
    index = 0
    while index < len(ranked):
        end = index + 1
        while end < len(ranked) and ranked[end][0] == ranked[index][0]:
            end += 1
        seen += end - index
        true_positive += sum(label == "ANOMALY" for _, label in ranked[index:end])
        recall = true_positive / positives
        precision = true_positive / seen
        result += (recall - previous_recall) * precision
        previous_recall = recall
        index = end
    return result


def select_threshold_from_validation(scores: ValidationScores) -> ThresholdSelection:
    _validated(scores.expected, scores.anomaly_softmax_probabilities)
    candidates = {0.0, 1.0, *scores.anomaly_softmax_probabilities}
    candidates.update(
        math.nextafter(score, 1.0) for score in scores.anomaly_softmax_probabilities if score < 1.0
    )
    ranked: list[tuple[float, float, float, MetricsReport]] = []
    for threshold in sorted(candidates):
        metrics = metrics_at_threshold(
            scores.expected, scores.anomaly_softmax_probabilities, threshold
        )
        ranked.append(
            (
                metrics.macro_f1,
                metrics.per_class["ANOMALY"].recall,
                -threshold,
                metrics,
            )
        )
    best = max(ranked, key=lambda item: (item[0], item[1], item[2]))
    return ThresholdSelection(
        threshold=-best[2],
        rule_version="agrimind-cv-validation-threshold-v1",
        validation_fingerprint=scores.validation_fingerprint,
        metrics=best[3],
    )


def evaluate_frozen_test(
    scores: HeldOutTestScores, evidence: FrozenEvaluationEvidence
) -> EvaluationReport:
    if not (evidence.model_frozen and evidence.preprocessing_frozen and evidence.threshold_frozen):
        raise ValueError("TEST evaluation requires frozen model, preprocessing and threshold")
    if not evidence.threshold.validation_fingerprint or not evidence.artifact_sha256:
        raise ValueError("TEST evaluation requires validation and artifact identity")
    metrics = metrics_at_threshold(
        scores.expected,
        scores.anomaly_softmax_probabilities,
        evidence.threshold.threshold,
    )
    return EvaluationReport(
        metrics=metrics,
        roc_auc=roc_auc(scores.expected, scores.anomaly_softmax_probabilities),
        average_precision=average_precision(scores.expected, scores.anomaly_softmax_probabilities),
        sample_count=len(scores.expected),
    )
