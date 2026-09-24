"""Export a trusted AGM-022 Joblib tree to the strict portable runtime format."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, cast

import joblib
from sklearn.tree import DecisionTreeClassifier

_ARTIFACT_VERSION = "v1"
_FORMAT = "agrimind-decision-tree-v1"
_DATASET_SHA256 = (
    "F776F34FC9C7BE1EEF59614DC41DDEADEF6FDE9DC11D908C4EC8A513D6AF4D2D"  # pragma: allowlist secret
)
_DECISION_THRESHOLD = 0.02040816326530612
_FEATURE_CONTRACT_VERSION = "v1"
_METHODOLOGY_VERSION = "baseline-v1"
_ORDERED_FEATURES = [
    "soil_moisture_index_0_100",
    "air_temperature_c",
    "air_relative_humidity_percent",
]


class ExportError(ValueError):
    """The trusted source does not match the approved AGM-022 result."""


class OutputExistsError(ExportError):
    """A generated output would be overwritten without explicit consent."""


def _object(value: object, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ExportError(f"{name} must be an object")
    return cast(dict[str, Any], value)


def _canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def export_portable_tree(
    *,
    joblib_path: Path,
    evaluation_path: Path,
    output_path: Path,
    digest_path: Path,
    overwrite: bool = False,
) -> dict[str, object]:
    """Export one reviewed tree; callers must supply a trusted local Joblib."""

    if not overwrite and (output_path.exists() or digest_path.exists()):
        raise OutputExistsError("output exists; pass --overwrite to replace generated outputs")
    try:
        evaluation = _object(json.loads(evaluation_path.read_text(encoding="utf-8")), "evaluation")
        model = joblib.load(joblib_path)
    except (OSError, json.JSONDecodeError) as error:
        raise ExportError("trusted export input is unreadable") from error
    if type(model) is not DecisionTreeClassifier:
        raise ExportError("selected model must be exactly DecisionTreeClassifier")

    selected = _object(evaluation.get("selected_model"), "selected_model")
    if (
        selected.get("family") != "decision_tree"
        or selected.get("candidate_id") != "decision_tree-00"
    ):
        raise ExportError("evaluation selected model is incompatible")
    ordered_features = evaluation.get("ordered_features")
    dataset = _object(evaluation.get("dataset"), "dataset")
    if (
        ordered_features != _ORDERED_FEATURES
        or evaluation.get("feature_contract_version") != _FEATURE_CONTRACT_VERSION
        or evaluation.get("methodology_version") != _METHODOLOGY_VERSION
        or str(dataset.get("sha256", "")).upper() != _DATASET_SHA256
        or selected.get("threshold") != _DECISION_THRESHOLD
    ):
        raise ExportError("evaluation provenance is incompatible")
    classes = [int(value) for value in model.classes_.tolist()]
    if classes != [0, 1] or model.n_features_in_ != len(ordered_features):
        raise ExportError("model classes or feature count are incompatible")

    tree = model.tree_
    nodes: list[dict[str, object]] = []
    for node_id in range(tree.node_count):
        left = int(tree.children_left[node_id])
        right = int(tree.children_right[node_id])
        if left == right:
            values = [float(item) for item in tree.value[node_id][0]]
            total = sum(values)
            if not math.isfinite(total) or total <= 0:
                raise ExportError("leaf class values are invalid")
            nodes.append(
                {
                    "id": node_id,
                    "kind": "leaf",
                    "positive_score": values[1] / total,
                }
            )
            continue
        feature_index = int(tree.feature[node_id])
        node_threshold = float(tree.threshold[node_id])
        if not 0 <= feature_index < len(ordered_features) or not math.isfinite(node_threshold):
            raise ExportError("split node is incompatible")
        nodes.append(
            {
                "feature_index": feature_index,
                "id": node_id,
                "kind": "split",
                "left": left,
                "right": right,
                "threshold": node_threshold,
            }
        )

    decision_threshold = selected.get("threshold")
    if isinstance(decision_threshold, bool) or not isinstance(decision_threshold, (int, float)):
        raise ExportError("evaluation threshold is invalid")
    artifact: dict[str, object] = {
        "artifact_version": _ARTIFACT_VERSION,
        "dataset_sha256": str(dataset.get("sha256", "")).upper(),
        "decision_threshold": float(decision_threshold),
        "feature_contract_version": str(evaluation.get("feature_contract_version", "")),
        "format": _FORMAT,
        "methodology_version": str(evaluation.get("methodology_version", "")),
        "model_class": type(model).__name__,
        "model_version": "irrigation-baseline-v1",
        "ordered_features": ordered_features,
        "target_classes": classes,
        "tree": {"node_count": tree.node_count, "nodes": nodes, "root_node": 0},
    }
    encoded = _canonical_bytes(artifact)
    digest = hashlib.sha256(encoded).hexdigest()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    digest_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(encoded)
    digest_path.write_text(f"{digest}\n", encoding="ascii")
    return artifact


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--joblib", required=True, type=Path)
    parser.add_argument("--evaluation", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--digest-output", required=True, type=Path)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        export_portable_tree(
            joblib_path=arguments.joblib,
            evaluation_path=arguments.evaluation,
            output_path=arguments.output,
            digest_path=arguments.digest_output,
            overwrite=arguments.overwrite,
        )
    except ExportError as error:
        print(f"export error: {error}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
