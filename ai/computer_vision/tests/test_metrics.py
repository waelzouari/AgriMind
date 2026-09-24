from agrimind_cv.metrics import classification_metrics


def test_metrics_and_zero_support_are_explicit() -> None:
    labels = ("NORMAL", "ANOMALY")
    report = classification_metrics(
        ["NORMAL", "NORMAL"],
        ["NORMAL", "ANOMALY"],
        labels,
    )
    assert report.accuracy == 0.5
    assert report.confusion_matrix == ((1, 1), (0, 0))
    assert report.per_class["ANOMALY"].support == 0
    assert report.per_class["ANOMALY"].recall == 0.0
