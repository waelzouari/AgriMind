"""Run the bounded AGM-022 baseline experiment without runtime inference concerns."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import platform
import re
from dataclasses import asdict, dataclass
from importlib.metadata import version
from pathlib import Path
from typing import Any, cast

import joblib  # type: ignore[import-untyped]
import sklearn
from sklearn.base import ClassifierMixin
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

from agrimind_irrigation.contract import load_contract
from agrimind_irrigation.evaluation import (
    MethodologicalEvaluationError,
    Metrics,
    ValidationCandidate,
    calculate_metrics,
    predictions_at_threshold,
    select_threshold,
    select_validation_candidate,
)
from agrimind_irrigation.methodology import (
    DatasetValidationError,
    MethodologyError,
    SplitValidationError,
    dataset_diagnostics,
    load_methodology,
    prepare_dataset,
    split_dataset,
    split_summary,
)


class OutputExistsError(ValueError):
    """A generated output would be overwritten without explicit permission."""


@dataclass(slots=True)
class CandidateRun:
    validation: ValidationCandidate
    fitted_model: ClassifierMixin


def _matrix(rows: tuple[Any, ...]) -> tuple[list[list[float]], list[int]]:
    return [list(row.features) for row in rows], [row.target for row in rows]


def positive_probabilities(model: ClassifierMixin, features: list[list[float]]) -> list[float]:
    classes = [int(label) for label in cast(Any, model).classes_]
    if classes.count(1) != 1:
        raise MethodologicalEvaluationError("fitted classifier must expose positive class 1")
    positive_index = classes.index(1)
    raw = cast(Any, model).predict_proba(features)
    return [float(value) for value in raw[:, positive_index].tolist()]


def _candidate_models(
    raw: dict[str, Any], seed: int
) -> list[tuple[str, dict[str, object], str, ClassifierMixin]]:
    configured = cast(dict[str, Any], raw["candidate_models"])
    candidates: list[tuple[str, dict[str, object], str, ClassifierMixin]] = []

    logistic = cast(dict[str, Any], configured["logistic_regression"])
    for c_value, class_weight in itertools.product(logistic["C"], logistic["class_weight"]):
        parameters = {"C": float(c_value), "class_weight": class_weight}
        model = Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "classifier",
                    LogisticRegression(
                        C=float(c_value),
                        class_weight=class_weight,
                        solver=str(logistic["solver"]),
                        max_iter=int(logistic["max_iter"]),
                        random_state=seed,
                    ),
                ),
            ]
        )
        candidates.append(("logistic_regression", parameters, "StandardScaler(train-only)", model))

    tree = cast(dict[str, Any], configured["decision_tree"])
    for depth, leaf, class_weight in itertools.product(
        tree["max_depth"], tree["min_samples_leaf"], tree["class_weight"]
    ):
        parameters = {
            "max_depth": int(depth),
            "min_samples_leaf": int(leaf),
            "class_weight": class_weight,
        }
        candidates.append(
            (
                "decision_tree",
                parameters,
                "none",
                DecisionTreeClassifier(random_state=seed, **parameters),
            )
        )

    forest = cast(dict[str, Any], configured["random_forest"])
    for trees, depth, leaf, class_weight in itertools.product(
        forest["n_estimators"],
        forest["max_depth"],
        forest["min_samples_leaf"],
        forest["class_weight"],
    ):
        parameters = {
            "n_estimators": int(trees),
            "max_depth": int(depth),
            "min_samples_leaf": int(leaf),
            "class_weight": class_weight,
            "n_jobs": int(forest["n_jobs"]),
        }
        candidates.append(
            (
                "random_forest",
                parameters,
                "none",
                RandomForestClassifier(random_state=seed, **parameters),
            )
        )
    return candidates


def fit_validation_candidates(
    raw: dict[str, Any], seed: int, train: tuple[Any, ...], validation: tuple[Any, ...]
) -> list[CandidateRun]:
    train_x, train_y = _matrix(train)
    validation_x, validation_y = _matrix(validation)
    runs: list[CandidateRun] = []
    family_complexity: dict[str, int] = {}
    for family, parameters, preprocessing, model in _candidate_models(raw, seed):
        complexity_rank = family_complexity.get(family, 0)
        family_complexity[family] = complexity_rank + 1
        model.fit(train_x, train_y)
        probabilities = positive_probabilities(model, validation_x)
        default_metrics = calculate_metrics(
            validation_y,
            predictions_at_threshold(probabilities, 0.5),
            probabilities,
        )
        threshold = select_threshold(validation_y, probabilities)
        identifier = f"{family}-{complexity_rank:02d}"
        runs.append(
            CandidateRun(
                ValidationCandidate(
                    candidate_id=identifier,
                    family=family,
                    hyperparameters=parameters,
                    preprocessing=preprocessing,
                    complexity_rank=complexity_rank,
                    default_threshold_metrics=default_metrics,
                    selected_threshold=threshold.threshold,
                    validation_metrics=threshold.metrics,
                ),
                model,
            )
        )
    return runs


def _dummy_metrics(rows: tuple[Any, ...]) -> Metrics:
    _, targets = _matrix(rows)
    probabilities = [0.0] * len(rows)
    return calculate_metrics(targets, [0] * len(rows), probabilities)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _write_json(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(result, indent=2, sort_keys=True) + "\n"
    # Public fingerprints are JSON-escaped to avoid credential scanners treating hashes as secrets.
    serialized = re.sub(
        r'(?<="sha256": ")([A-F0-9]{64})(?=")',
        lambda match: match.group(1).replace("E", r"\u0045", 1),
        serialized,
    )
    path.write_text(serialized, encoding="utf-8")


def run_experiment(
    *,
    contract_path: Path,
    methodology_path: Path,
    dataset_path: Path,
    expected_sha256: str,
    result_path: Path,
    artifact_path: Path | None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Train on train, select on validation, then evaluate the frozen model once on test."""

    outputs = [result_path, *([artifact_path] if artifact_path is not None else [])]
    if not overwrite and any(path.exists() for path in outputs):
        raise OutputExistsError("output exists; pass --overwrite to replace generated outputs")
    methodology = load_methodology(methodology_path)
    contract = load_contract(contract_path)
    prepared = prepare_dataset(
        contract,
        methodology,
        dataset_path,
        expected_sha256=expected_sha256,
    )
    split = split_dataset(prepared, methodology)
    validation_dummy = _dummy_metrics(split.validation)
    candidate_runs = fit_validation_candidates(
        methodology.raw, methodology.random_seed, split.train, split.validation
    )
    selected_validation = select_validation_candidate(
        [run.validation for run in candidate_runs], validation_dummy
    )
    selected_run = next(
        run
        for run in candidate_runs
        if run.validation.candidate_id == selected_validation.candidate_id
    )

    # This is the only final-test prediction path. The fitted estimator is reused without refit.
    test_x, test_y = _matrix(split.test)
    test_probabilities = positive_probabilities(selected_run.fitted_model, test_x)
    test_metrics = calculate_metrics(
        test_y,
        predictions_at_threshold(test_probabilities, selected_validation.selected_threshold),
        test_probabilities,
    )
    test_dummy = _dummy_metrics(split.test)

    artifact: dict[str, object] = {
        "generated": False,
        "format": "joblib",
        "trust_warning": "Only load trusted project-produced artifacts.",
    }
    if artifact_path is not None:
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(selected_run.fitted_model, artifact_path)
        artifact = {
            **artifact,
            "generated": True,
            "path": artifact_path.as_posix(),
            "sha256": _sha256(artifact_path),
            "trained_data_scope": "train_only",
        }

    diagnostics = dataset_diagnostics(prepared, split)
    result: dict[str, Any] = {
        "artifact": artifact,
        "candidates": [asdict(run.validation) for run in candidate_runs],
        "dataset": {
            "sha256": prepared.audit.dataset_sha256,
            "raw_rows": prepared.audit.row_count,
            "invalid_rows": len(prepared.invalid_rows),
            "usable_rows": len(prepared.rows),
            "invalid_row_summary": {
                "Humidity": sum(
                    "invalid_or_missing:Humidity" in row.reasons for row in prepared.invalid_rows
                ),
                "Soil Moisture": sum(
                    "invalid_or_missing:Soil Moisture" in row.reasons
                    for row in prepared.invalid_rows
                ),
                "Temperature": sum(
                    "invalid_or_missing:Temperature" in row.reasons for row in prepared.invalid_rows
                ),
                "irrigation": sum(
                    "invalid_or_missing:irrigation" in row.reasons for row in prepared.invalid_rows
                ),
            },
            "duplicates": {
                "exact": prepared.audit.exact_duplicate_rows,
                "excluding_time": prepared.audit.duplicates_without_time,
                "feature_and_target": prepared.audit.feature_target_duplicate_rows,
            },
            **diagnostics,
        },
        "dummy": {
            "validation": validation_dummy.to_dict(),
            "test": test_dummy.to_dict(),
        },
        "feature_contract_version": contract.version,
        "library_versions": {
            "joblib": version("joblib"),
            "numpy": version("numpy"),
            "python": platform.python_version(),
            "scikit_learn": sklearn.__version__,
            "scipy": version("scipy"),
        },
        "methodology_version": methodology.version,
        "model_fit_scope": "train_only",
        "no_refit_before_test": True,
        "ordered_features": [feature.canonical_name for feature in contract.ordered_features],
        "random_seed": methodology.random_seed,
        "selected_model": {
            "candidate_id": selected_validation.candidate_id,
            "family": selected_validation.family,
            "hyperparameters": selected_validation.hyperparameters,
            "preprocessing": selected_validation.preprocessing,
            "threshold": selected_validation.selected_threshold,
            "validation_metrics": selected_validation.validation_metrics.to_dict(),
            "test_metrics": test_metrics.to_dict(),
        },
        "selection_source": "validation",
        "split": split_summary(split),
        "target": {"name": contract.target_name, "encoding": {"0": False, "1": True}},
        "test_evaluation_count": 1,
        "test_used_for_selection": False,
        "limitations": [
            "Performance is limited to the audited Mendeley MVP dataset and documented split.",
            "The split has substantial temporal target-distribution shift.",
            "The soil-moisture value is an undocumented 0-100 proxy calibration.",
            "Identical feature vectors can carry conflicting labels.",
            (
                "Features and irrigation status share a timestamp; causal pre-actuation "
                "ordering is not independently proven."
            ),
            (
                "Perfect held-out scores are consistent with reconstruction of a simple "
                "dataset status rule, not demonstrated agronomic generalization."
            ),
            (
                "Decision-tree leaf frequencies are model scores, not validated irrigation "
                "probabilities."
            ),
            "No agronomic, production, hardware-latency, or resource-usage claim is made.",
        ],
    }
    _write_json(result_path, result)
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--methodology", required=True, type=Path)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--result", required=True, type=Path)
    parser.add_argument("--artifact", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    arguments = parser.parse_args(argv)
    try:
        run_experiment(
            contract_path=arguments.contract,
            methodology_path=arguments.methodology,
            dataset_path=arguments.dataset,
            expected_sha256=arguments.expected_sha256,
            result_path=arguments.result,
            artifact_path=arguments.artifact,
            overwrite=arguments.overwrite,
        )
    except OutputExistsError as error:
        print(f"output error: {error}")
        return 6
    except SplitValidationError as error:
        print(f"split error: {error}")
        return 4
    except MethodologicalEvaluationError as error:
        print(f"training error: {error}")
        return 5
    except (MethodologyError, json.JSONDecodeError, KeyError) as error:
        parser.error(str(error))
    except (DatasetValidationError, OSError, ValueError) as error:
        print(f"dataset error: {error}")
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
