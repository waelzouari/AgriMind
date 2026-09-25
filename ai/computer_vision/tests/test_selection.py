from agrimind_cv.metrics import classification_metrics
from agrimind_cv.selection import BASELINE_ID, CANDIDATE_ID, select_model


def report(expected: list[str], predicted: list[str]):  # type: ignore[no-untyped-def]
    return classification_metrics(expected, predicted, ("NORMAL", "ANOMALY"))


def test_candidate_wins_only_on_validation_rule() -> None:
    baseline = report(["NORMAL", "ANOMALY"], ["NORMAL", "NORMAL"])
    candidate = report(["NORMAL", "ANOMALY"], ["NORMAL", "ANOMALY"])
    evidence = select_model(baseline, candidate)
    assert evidence.selected_model == CANDIDATE_ID
    assert evidence.test_evaluated is False


def test_baseline_wins_exact_tie_for_simplicity() -> None:
    value = report(["NORMAL", "ANOMALY"], ["NORMAL", "ANOMALY"])
    assert select_model(value, value).selected_model == BASELINE_ID


def test_unknown_selection_rule_fails_closed() -> None:
    value = report(["NORMAL", "ANOMALY"], ["NORMAL", "ANOMALY"])
    try:
        select_model(value, value, rule_version="unknown")
    except ValueError as error:
        assert "unsupported" in str(error)
    else:
        raise AssertionError("unknown selection rule must fail")
