from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sklearn.pipeline import Pipeline
from test_methodology import (
    METHODOLOGY_SOURCE,
    configured_boundaries,
    valid_row,
    write_dataset,
)

from agrimind_irrigation.methodology import TrainingRow
from agrimind_irrigation.training import (
    OutputExistsError,
    fit_validation_candidates,
    positive_probabilities,
    run_experiment,
)


def compact_methodology(path: Path) -> dict[str, object]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["candidate_models"]["logistic_regression"]["C"] = [1.0]
    raw["candidate_models"]["decision_tree"]["max_depth"] = [2]
    raw["candidate_models"]["decision_tree"]["min_samples_leaf"] = [2]
    raw["candidate_models"]["random_forest"]["n_estimators"] = [5]
    raw["candidate_models"]["random_forest"]["max_depth"] = [2]
    raw["candidate_models"]["random_forest"]["min_samples_leaf"] = [2]
    return raw


def test_logistic_scaler_is_fitted_only_from_train() -> None:
    origin = datetime(2023, 1, 1)
    train = tuple(
        TrainingRow(index, origin + timedelta(minutes=index), (float(index), 10.0, 20.0), index % 2)
        for index in range(1, 9)
    )
    validation = tuple(
        TrainingRow(
            index, origin + timedelta(days=1, minutes=index), (1000.0, 10.0, 20.0), index % 2
        )
        for index in range(9, 13)
    )
    raw = compact_methodology(METHODOLOGY_SOURCE)

    runs = fit_validation_candidates(raw, 42, train, validation)
    repeated_runs = fit_validation_candidates(raw, 42, train, validation)
    logistic = next(run for run in runs if run.validation.family == "logistic_regression")

    assert [asdict(run.validation) for run in runs] == [
        asdict(run.validation) for run in repeated_runs
    ]
    assert isinstance(logistic.fitted_model, Pipeline)
    scaler = logistic.fitted_model.named_steps["scaler"]
    assert scaler.mean_[0] == pytest.approx(4.5)
    assert scaler.mean_[0] != pytest.approx(1000.0)
    assert all(
        not isinstance(run.fitted_model, Pipeline)
        for run in runs
        if run.validation.family in {"decision_tree", "random_forest"}
    )

    for run in runs:
        if run.validation.family == "logistic_regression":
            assert run.fitted_model.named_steps["scaler"].n_samples_seen_ == len(train)
        elif run.validation.family == "decision_tree":
            assert run.fitted_model.tree_.n_node_samples[0] == len(train)
        else:
            assert all(
                len(indices) == len(train) for indices in run.fitted_model.estimators_samples_
            )


def test_positive_probability_uses_the_class_label_not_a_fixed_column() -> None:
    class Column:
        def __init__(self, values: list[float]) -> None:
            self.values = values

        def tolist(self) -> list[float]:
            return self.values

    class Matrix:
        def __getitem__(self, key: tuple[slice, int]) -> Column:
            assert key[0] == slice(None)
            return Column([0.8, 0.3] if key[1] == 0 else [0.2, 0.7])

    class ReversedClassifier:
        classes_ = (1, 0)

        def predict_proba(self, features: list[list[float]]) -> Matrix:
            assert len(features) == 2
            return Matrix()

    assert positive_probabilities(
        ReversedClassifier(),  # type: ignore[arg-type]
        [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]],
    ) == [0.8, 0.3]


def test_end_to_end_result_artifact_and_overwrite_guard(tmp_path: Path) -> None:
    dataset_path = tmp_path / "fixture.csv"
    rows: list[list[object]] = []
    for day in (3, 4, 5):
        for index in range(12):
            rows.append(
                valid_row(
                    datetime(2023, 1, day, index),
                    index % 2,
                    moisture=20 if index % 2 else 80,
                )
            )
    digest = write_dataset(dataset_path, rows)
    contract_path, methodology_path = configured_boundaries(tmp_path, digest)
    methodology_path.write_text(json.dumps(compact_methodology(methodology_path)), encoding="utf-8")
    result_path = tmp_path / "result.json"
    artifact_path = tmp_path / "model.joblib"

    result = run_experiment(
        contract_path=contract_path,
        methodology_path=methodology_path,
        dataset_path=dataset_path,
        expected_sha256=digest,
        result_path=result_path,
        artifact_path=artifact_path,
    )

    assert result["selection_source"] == "validation"
    assert result["test_used_for_selection"] is False
    assert result["test_evaluation_count"] == 1
    assert result["model_fit_scope"] == "train_only"
    assert result["no_refit_before_test"] is True
    assert result["methodology_version"] == "baseline-v1"
    assert result["feature_contract_version"] == "v1"
    assert result["ordered_features"] == [
        "soil_moisture_index_0_100",
        "air_temperature_c",
        "air_relative_humidity_percent",
    ]
    assert result["target"]["encoding"] == {"0": False, "1": True}
    assert set(result["library_versions"]) == {
        "joblib",
        "numpy",
        "python",
        "scikit_learn",
        "scipy",
    }
    assert result["artifact"]["sha256"]
    assert result_path.read_text(encoding="utf-8").endswith("\n")
    assert "source_row" not in result_path.read_text(encoding="utf-8")
    with pytest.raises(OutputExistsError):
        run_experiment(
            contract_path=contract_path,
            methodology_path=methodology_path,
            dataset_path=dataset_path,
            expected_sha256=digest,
            result_path=result_path,
            artifact_path=artifact_path,
        )
