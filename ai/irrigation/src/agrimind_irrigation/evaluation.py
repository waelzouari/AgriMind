"""Metrics and validation-only selection rules for AGM-022."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Protocol

from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


class MethodologicalEvaluationError(ValueError):
    """A metric or selection operation is methodologically invalid."""


class FittedProbabilityModel(Protocol):
    def predict_proba(self, features: list[list[float]]) -> object: ...


@dataclass(frozen=True, slots=True)
class Metrics:
    accuracy: float
    balanced_accuracy: float
    positive_precision: float
    positive_recall: float
    positive_f1: float
    average_precision: float
    roc_auc: float
    predicted_positive_rate: float
    confusion_matrix: dict[str, int]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ThresholdResult:
    threshold: float
    metrics: Metrics


@dataclass(frozen=True, slots=True)
class ValidationCandidate:
    candidate_id: str
    family: str
    hyperparameters: dict[str, object]
    preprocessing: str
    complexity_rank: int
    default_threshold_metrics: Metrics
    selected_threshold: float
    validation_metrics: Metrics


def predictions_at_threshold(probabilities: list[float], threshold: float) -> list[int]:
    return [int(probability >= threshold) for probability in probabilities]


def calculate_metrics(
    targets: list[int], predictions: list[int], probabilities: list[float]
) -> Metrics:
    if len(targets) != len(predictions) or len(targets) != len(probabilities) or not targets:
        raise MethodologicalEvaluationError("targets, predictions, and probabilities must align")
    if set(targets) != {0, 1}:
        raise MethodologicalEvaluationError("metrics require both target classes")
    if any(not math.isfinite(value) for value in probabilities):
        raise MethodologicalEvaluationError("probabilities must be finite")
    matrix = confusion_matrix(targets, predictions, labels=[0, 1])
    tn, fp, fn, tp = (int(value) for value in matrix.ravel())
    values = Metrics(
        accuracy=float(accuracy_score(targets, predictions)),
        balanced_accuracy=float(balanced_accuracy_score(targets, predictions)),
        positive_precision=float(precision_score(targets, predictions, zero_division=0)),
        positive_recall=float(recall_score(targets, predictions, zero_division=0)),
        positive_f1=float(f1_score(targets, predictions, zero_division=0)),
        average_precision=float(average_precision_score(targets, probabilities)),
        roc_auc=float(roc_auc_score(targets, probabilities)),
        predicted_positive_rate=sum(predictions) / len(predictions),
        confusion_matrix={"tn": tn, "fp": fp, "fn": fn, "tp": tp},
    )
    scalar_values = (
        values.accuracy,
        values.balanced_accuracy,
        values.positive_precision,
        values.positive_recall,
        values.positive_f1,
        values.average_precision,
        values.roc_auc,
        values.predicted_positive_rate,
    )
    if any(not math.isfinite(value) for value in scalar_values):
        raise MethodologicalEvaluationError("all metrics must be finite")
    return values


def select_threshold(targets: list[int], probabilities: list[float]) -> ThresholdResult:
    candidates = sorted({0.5, *probabilities})
    evaluated = [
        ThresholdResult(
            threshold,
            calculate_metrics(
                targets,
                predictions_at_threshold(probabilities, threshold),
                probabilities,
            ),
        )
        for threshold in candidates
    ]
    return max(
        evaluated,
        key=lambda item: (
            item.metrics.positive_f1,
            item.metrics.balanced_accuracy,
            -abs(item.threshold - 0.5),
            -item.threshold,
        ),
    )


def select_validation_candidate(
    candidates: list[ValidationCandidate], dummy_validation: Metrics
) -> ValidationCandidate:
    """Select from validation records only; test metrics are not accepted by this API."""

    eligible = [
        candidate
        for candidate in candidates
        if candidate.validation_metrics.positive_f1 > dummy_validation.positive_f1
        and candidate.validation_metrics.balanced_accuracy > dummy_validation.balanced_accuracy
    ]
    if not eligible:
        raise MethodologicalEvaluationError(
            "no candidate beats dummy on both primary validation metrics"
        )
    family_rank = {"logistic_regression": 0, "decision_tree": 1, "random_forest": 2}
    return max(
        eligible,
        key=lambda candidate: (
            candidate.validation_metrics.positive_f1,
            candidate.validation_metrics.balanced_accuracy,
            -family_rank[candidate.family],
            -candidate.complexity_rank,
        ),
    )
