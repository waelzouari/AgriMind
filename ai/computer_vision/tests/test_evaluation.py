from __future__ import annotations

from dataclasses import replace

import pytest

from agrimind_cv.evaluation import (
    FrozenEvaluationEvidence,
    HeldOutTestScores,
    ValidationScores,
    average_precision,
    evaluate_frozen_test,
    roc_auc,
    select_threshold_from_validation,
)


def validation() -> ValidationScores:
    return ValidationScores(
        ("NORMAL", "NORMAL", "ANOMALY", "ANOMALY"),
        (0.1, 0.4, 0.6, 0.9),
        "v" * 64,
    )


def test_metrics_auc_average_precision_and_threshold_are_correct() -> None:
    scores = validation()
    selection = select_threshold_from_validation(scores)
    assert selection.threshold == pytest.approx(0.4000000000000001)
    assert selection.metrics.accuracy == 1
    assert selection.metrics.confusion_matrix == ((2, 0), (0, 2))
    assert selection.metrics.per_class["ANOMALY"].support == 2
    assert roc_auc(scores.expected, scores.anomaly_softmax_probabilities) == 1
    assert average_precision(scores.expected, scores.anomaly_softmax_probabilities) == 1


def test_auc_and_average_precision_handle_ties_deterministically() -> None:
    expected = ("NORMAL", "ANOMALY", "NORMAL", "ANOMALY")
    scores = (0.2, 0.5, 0.5, 0.8)
    assert roc_auc(expected, scores) == pytest.approx(0.875)
    assert average_precision(expected, scores) == pytest.approx(5 / 6)


@pytest.mark.parametrize(
    ("expected", "scores"),
    [
        ((), ()),
        (("NORMAL",), (0.1, 0.2)),
        (("OTHER",), (0.1,)),
        (("NORMAL",), (float("nan"),)),
        (("NORMAL",), (float("inf"),)),
        (("NORMAL",), (-0.1,)),
        (("NORMAL",), (1.1,)),
    ],
)
def test_invalid_score_inputs_are_rejected(
    expected: tuple[str, ...], scores: tuple[float, ...]
) -> None:
    with pytest.raises(ValueError):
        select_threshold_from_validation(ValidationScores(expected, scores, "v" * 64))


def test_threshold_tie_prefers_anomaly_recall_then_lower_threshold() -> None:
    selection = select_threshold_from_validation(
        ValidationScores(("NORMAL", "ANOMALY"), (0.5, 0.5), "v" * 64)
    )
    assert selection.threshold == 0.0
    assert selection.metrics.per_class["ANOMALY"].recall == 1


def test_test_evaluation_requires_all_frozen_evidence() -> None:
    threshold = select_threshold_from_validation(validation())
    evidence = FrozenEvaluationEvidence(
        "a" * 64,
        "1.0.0",
        "agrimind-cv-mobilenet-v2-preprocessing-v1",
        threshold,
    )
    report = evaluate_frozen_test(HeldOutTestScores(("NORMAL", "ANOMALY"), (0.2, 0.8)), evidence)
    assert report.sample_count == 2
    assert report.metrics.macro_f1 == 1
    with pytest.raises(ValueError, match="frozen"):
        evaluate_frozen_test(
            HeldOutTestScores(("NORMAL", "ANOMALY"), (0.2, 0.8)),
            replace(evidence, threshold_frozen=False),
        )


def test_threshold_api_only_accepts_validation_scores() -> None:
    with pytest.raises((AttributeError, TypeError)):
        select_threshold_from_validation(  # type: ignore[arg-type]
            HeldOutTestScores(("NORMAL", "ANOMALY"), (0.2, 0.8))
        )
