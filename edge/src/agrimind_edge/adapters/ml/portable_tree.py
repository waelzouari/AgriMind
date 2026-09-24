"""Strict standard-library runtime for the versioned AGM-022 tree artifact."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import cast

from agrimind_edge.application.inference_ports import (
    ArtifactIntegrityError,
    ModelCompatibilityError,
    ModelInferenceError,
    ModelUnavailableError,
)
from agrimind_edge.domain.irrigation_inference import (
    DATASET_SHA256,
    DECISION_THRESHOLD,
    FEATURE_CONTRACT_VERSION,
    METHODOLOGY_VERSION,
    MODEL_VERSION,
    ORDERED_FEATURES,
    IrrigationFeatureVector,
    ModelPrediction,
)

_ARTIFACT_VERSION = "v1"
_FORMAT = "agrimind-decision-tree-v1"
_MODEL_CLASS = "DecisionTreeClassifier"
_ARTIFACT_NAME = "baseline-v1.json"
_DIGEST_NAME = "baseline-v1.sha256"


@dataclass(frozen=True, slots=True)
class _SplitNode:
    feature_index: int
    threshold: float
    left: int
    right: int


@dataclass(frozen=True, slots=True)
class _LeafNode:
    positive_score: float


_Node = _SplitNode | _LeafNode


@dataclass(frozen=True, slots=True)
class _PortableTree:
    nodes: tuple[_Node, ...]
    threshold: float


class PortableTreeModelAdapter:
    """Load one trusted JSON tree once and evaluate it without ML libraries."""

    def __init__(
        self,
        artifact_path: Path | None = None,
        digest_path: Path | None = None,
    ) -> None:
        if (artifact_path is None) != (digest_path is None):
            raise ValueError("artifact and digest paths must be supplied together")
        self._artifact_path = artifact_path
        self._digest_path = digest_path
        self._tree: _PortableTree | None = None

    def predict(self, features: IrrigationFeatureVector) -> ModelPrediction:
        tree = self._load()
        values = features.as_ordered_tuple()
        node_index = 0
        try:
            for _ in range(len(tree.nodes)):
                node = tree.nodes[node_index]
                if isinstance(node, _LeafNode):
                    return ModelPrediction(
                        model_version=MODEL_VERSION,
                        feature_contract_version=FEATURE_CONTRACT_VERSION,
                        methodology_version=METHODOLOGY_VERSION,
                        score=node.positive_score,
                        threshold=tree.threshold,
                    )
                node_index = (
                    node.left if values[node.feature_index] <= node.threshold else node.right
                )
        except (IndexError, TypeError) as error:
            raise ModelInferenceError("portable model traversal failed") from error
        raise ModelInferenceError("portable model traversal did not reach a leaf")

    def _load(self) -> _PortableTree:
        if self._tree is not None:
            return self._tree
        artifact_bytes, digest_text = self._read_assets()
        expected_digest = digest_text.strip().lower()
        if len(expected_digest) != 64 or any(
            character not in "0123456789abcdef" for character in expected_digest
        ):
            raise ArtifactIntegrityError("artifact digest is invalid")
        actual_digest = hashlib.sha256(artifact_bytes).hexdigest()
        if actual_digest != expected_digest:
            raise ArtifactIntegrityError("artifact digest does not match")
        try:
            raw = json.loads(
                artifact_bytes,
                object_pairs_hook=_unique_object,
                parse_constant=lambda value: _reject_constant(value),
            )
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
            raise ModelCompatibilityError("artifact is not strict JSON") from error
        self._tree = _parse_artifact(raw)
        return self._tree

    def _read_assets(self) -> tuple[bytes, str]:
        try:
            if self._artifact_path is not None and self._digest_path is not None:
                return (
                    self._artifact_path.read_bytes(),
                    self._digest_path.read_text(encoding="ascii"),
                )
            resources = files("agrimind_edge.adapters.ml.models")
            return (
                resources.joinpath(_ARTIFACT_NAME).read_bytes(),
                resources.joinpath(_DIGEST_NAME).read_text(encoding="ascii"),
            )
        except (OSError, UnicodeError) as error:
            raise ModelUnavailableError("portable model asset is unavailable") from error


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant is forbidden: {value}")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _object(value: object, name: str, keys: set[str]) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ModelCompatibilityError(f"{name} has incompatible fields")
    return cast(dict[str, object], value)


def _number(value: object, name: str, *, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ModelCompatibilityError(f"{name} must be numeric")
    numeric = float(value)
    if not math.isfinite(numeric) or not minimum <= numeric <= maximum:
        raise ModelCompatibilityError(f"{name} is outside its supported range")
    return numeric


def _integer(value: object, name: str, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ModelCompatibilityError(f"{name} must be a supported integer")
    return value


def _parse_artifact(value: object) -> _PortableTree:
    raw = _object(
        value,
        "artifact",
        {
            "artifact_version",
            "dataset_sha256",
            "decision_threshold",
            "feature_contract_version",
            "format",
            "methodology_version",
            "model_class",
            "model_version",
            "ordered_features",
            "target_classes",
            "tree",
        },
    )
    expected = {
        "artifact_version": _ARTIFACT_VERSION,
        "dataset_sha256": DATASET_SHA256,
        "feature_contract_version": FEATURE_CONTRACT_VERSION,
        "format": _FORMAT,
        "methodology_version": METHODOLOGY_VERSION,
        "model_class": _MODEL_CLASS,
        "model_version": MODEL_VERSION,
    }
    if any(raw[name] != expected_value for name, expected_value in expected.items()):
        raise ModelCompatibilityError("artifact metadata is incompatible")
    if raw["ordered_features"] != list(ORDERED_FEATURES):
        raise ModelCompatibilityError("artifact feature order is incompatible")
    if raw["target_classes"] != [0, 1]:
        raise ModelCompatibilityError("artifact target classes are incompatible")
    threshold = _number(raw["decision_threshold"], "decision_threshold", minimum=0.0, maximum=1.0)
    if threshold != DECISION_THRESHOLD:
        raise ModelCompatibilityError("artifact decision threshold is incompatible")

    tree = _object(raw["tree"], "tree", {"node_count", "nodes", "root_node"})
    node_values = tree["nodes"]
    if not isinstance(node_values, list) or not node_values:
        raise ModelCompatibilityError("tree nodes must be a non-empty list")
    node_count = _integer(tree["node_count"], "node_count", minimum=1, maximum=100)
    root = _integer(tree["root_node"], "root_node", minimum=0, maximum=node_count - 1)
    if node_count != len(node_values) or root != 0:
        raise ModelCompatibilityError("tree shape is incompatible")

    nodes: list[_Node] = []
    for index, item in enumerate(node_values):
        if not isinstance(item, dict) or item.get("id") != index:
            raise ModelCompatibilityError("tree node identifiers must be contiguous")
        kind = item.get("kind")
        if kind == "leaf":
            leaf = _object(item, "leaf", {"id", "kind", "positive_score"})
            nodes.append(
                _LeafNode(
                    _number(
                        leaf["positive_score"],
                        "positive_score",
                        minimum=0.0,
                        maximum=1.0,
                    )
                )
            )
        elif kind == "split":
            split = _object(
                item,
                "split",
                {"feature_index", "id", "kind", "left", "right", "threshold"},
            )
            nodes.append(
                _SplitNode(
                    feature_index=_integer(
                        split["feature_index"],
                        "feature_index",
                        minimum=0,
                        maximum=len(ORDERED_FEATURES) - 1,
                    ),
                    threshold=_number(
                        split["threshold"],
                        "node threshold",
                        minimum=-1e12,
                        maximum=1e12,
                    ),
                    left=_integer(split["left"], "left", minimum=0, maximum=node_count - 1),
                    right=_integer(split["right"], "right", minimum=0, maximum=node_count - 1),
                )
            )
        else:
            raise ModelCompatibilityError("tree node kind is incompatible")
    _validate_graph(tuple(nodes), root)
    return _PortableTree(tuple(nodes), threshold)


def _validate_graph(nodes: tuple[_Node, ...], root: int) -> None:
    visiting: set[int] = set()
    visited: set[int] = set()

    def visit(index: int) -> None:
        if index in visiting:
            raise ModelCompatibilityError("tree contains a cycle")
        if index in visited:
            return
        visiting.add(index)
        node = nodes[index]
        if isinstance(node, _SplitNode):
            visit(node.left)
            visit(node.right)
        visiting.remove(index)
        visited.add(index)

    visit(root)
    if len(visited) != len(nodes):
        raise ModelCompatibilityError("tree contains unreachable nodes")
