from __future__ import annotations

import inspect

import pytest

from agrimind_irrigation.evaluation import (
    Metrics,
    ValidationCandidate,
    calculate_metrics,
    select_threshold,
    select_validation_candidate,
)


def metric(f1: float, balanced: float) -> Metrics:
    return Metrics(0.5, balanced, 0.5, 0.5, f1, 0.5, 0.5, 0.5, {"tn": 1, "fp": 1, "fn": 1, "tp": 1})


def candidate(family: str, rank: int, f1: float, balanced: float) -> ValidationCandidate:
    values = metric(f1, balanced)
    return ValidationCandidate(f"{family}-{rank}", family, {}, "none", rank, values, 0.5, values)


def test_metrics_include_expected_confusion_and_zero_division_policy() -> None:
    values = calculate_metrics([0, 0, 1, 1], [0, 0, 0, 0], [0.1, 0.2, 0.3, 0.4])

    assert values.confusion_matrix == {"tn": 2, "fp": 0, "fn": 2, "tp": 0}
    assert values.accuracy == 0.5
    assert values.balanced_accuracy == 0.5
    assert values.positive_precision == 0
    assert values.positive_recall == 0
    assert values.positive_f1 == 0
    assert values.predicted_positive_rate == 0
    assert values.average_precision == pytest.approx(1.0)
    assert values.roc_auc == pytest.approx(1.0)


def test_threshold_tie_break_is_deterministic() -> None:
    selected = select_threshold([0, 1], [0.4, 0.6])

    assert selected.threshold == pytest.approx(0.5)
    assert selected.metrics.positive_f1 == 1.0


def test_threshold_candidates_handle_bounds_duplicates_and_constant_scores() -> None:
    bounded = select_threshold([0, 1], [0.0, 1.0])
    constant = select_threshold([0, 1], [0.5, 0.5])

    assert bounded.threshold == pytest.approx(0.5)
    assert bounded.metrics.positive_f1 == 1.0
    assert constant.threshold == pytest.approx(0.5)
    with pytest.raises(ValueError, match="align"):
        select_threshold([], [])
    with pytest.raises(ValueError, match="finite"):
        select_threshold([0, 1], [0.2, float("nan")])


def test_selection_uses_primary_validation_metrics_then_simplicity() -> None:
    dummy = metric(0.0, 0.5)
    selected = select_validation_candidate(
        [
            candidate("random_forest", 0, 0.8, 0.7),
            candidate("decision_tree", 0, 0.8, 0.7),
            candidate("logistic_regression", 0, 0.8, 0.7),
        ],
        dummy,
    )

    assert selected.family == "logistic_regression"
    assert tuple(inspect.signature(select_validation_candidate).parameters) == (
        "candidates",
        "dummy_validation",
    )
