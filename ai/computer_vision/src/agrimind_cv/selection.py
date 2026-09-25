"""Validation-only, versioned model-selection policy."""

from __future__ import annotations

from dataclasses import dataclass

from agrimind_cv.metrics import MetricsReport

SELECTION_RULE_VERSION = "agrimind-cv-validation-selection-v1"
BASELINE_ID = "mean_rgb_centroid_baseline"
CANDIDATE_ID = "mobilenet_v2"


@dataclass(frozen=True, slots=True)
class SelectionEvidence:
    rule_version: str
    selected_model: str
    reason: str
    baseline_validation: MetricsReport
    candidate_validation: MetricsReport
    test_evaluated: bool = False


def select_model(
    baseline: MetricsReport,
    candidate: MetricsReport,
    *,
    rule_version: str = SELECTION_RULE_VERSION,
) -> SelectionEvidence:
    if rule_version != SELECTION_RULE_VERSION:
        raise ValueError("unsupported model-selection rule")
    baseline_score = (baseline.macro_f1, baseline.accuracy)
    candidate_score = (candidate.macro_f1, candidate.accuracy)
    if candidate_score > baseline_score:
        return SelectionEvidence(
            rule_version,
            CANDIDATE_ID,
            "candidate wins by validation macro-F1, then validation accuracy",
            baseline,
            candidate,
        )
    return SelectionEvidence(
        rule_version,
        BASELINE_ID,
        "baseline wins or ties; simplicity is the tie-breaker",
        baseline,
        candidate,
    )
