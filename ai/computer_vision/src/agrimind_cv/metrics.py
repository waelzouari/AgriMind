"""Dependency-light binary classification metrics."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ClassMetrics:
    precision: float
    recall: float
    f1: float
    support: int


@dataclass(frozen=True, slots=True)
class MetricsReport:
    accuracy: float
    macro_precision: float
    macro_recall: float
    macro_f1: float
    per_class: dict[str, ClassMetrics]
    confusion_matrix: tuple[tuple[int, ...], ...]


def classification_metrics(
    expected: list[str], predicted: list[str], labels: tuple[str, ...]
) -> MetricsReport:
    if not expected or len(expected) != len(predicted):
        raise ValueError("expected and predicted labels must be non-empty and equal length")
    if len(set(labels)) != len(labels) or any(
        value not in labels for value in expected + predicted
    ):
        raise ValueError("all labels must belong to the unique declared label set")
    index = {label: position for position, label in enumerate(labels)}
    matrix = [[0 for _ in labels] for _ in labels]
    for actual, guess in zip(expected, predicted, strict=True):
        matrix[index[actual]][index[guess]] += 1
    per_class: dict[str, ClassMetrics] = {}
    for position, label in enumerate(labels):
        true_positive = matrix[position][position]
        false_positive = sum(row[position] for row in matrix) - true_positive
        support = sum(matrix[position])
        precision = (
            true_positive / (true_positive + false_positive)
            if true_positive + false_positive
            else 0.0
        )
        recall = true_positive / support if support else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = ClassMetrics(precision, recall, f1, support)
    values = tuple(per_class.values())
    return MetricsReport(
        accuracy=sum(matrix[i][i] for i in range(len(labels))) / len(expected),
        macro_precision=sum(value.precision for value in values) / len(values),
        macro_recall=sum(value.recall for value in values) / len(values),
        macro_f1=sum(value.f1 for value in values) / len(values),
        per_class=per_class,
        confusion_matrix=tuple(tuple(row) for row in matrix),
    )
