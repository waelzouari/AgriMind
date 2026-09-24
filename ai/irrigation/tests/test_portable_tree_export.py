from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import joblib
import pytest
from sklearn.tree import DecisionTreeClassifier

from agrimind_irrigation.export_portable_tree import export_portable_tree

ROOT = Path(__file__).parents[1]
REPOSITORY_ROOT = ROOT.parents[1]
VERSIONED_MODEL = REPOSITORY_ROOT / "edge/src/agrimind_edge/adapters/ml/models/baseline-v1.json"
VERSIONED_DIGEST = VERSIONED_MODEL.with_suffix(".sha256")
LOCAL_JOBLIB = ROOT / "artifacts/baseline-v1.joblib"
EVALUATION = ROOT / "evaluation/baseline-v1.json"
DATASET_SHA256 = (
    "F776F34FC9C7BE1EEF59614DC41DDEADEF6FDE9DC11D908C4EC8A513D6AF4D2D"  # pragma: allowlist secret
)


def _evaluation(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "dataset": {"sha256": DATASET_SHA256},
                "feature_contract_version": "v1",
                "methodology_version": "baseline-v1",
                "ordered_features": [
                    "soil_moisture_index_0_100",
                    "air_temperature_c",
                    "air_relative_humidity_percent",
                ],
                "selected_model": {
                    "candidate_id": "decision_tree-00",
                    "family": "decision_tree",
                    "threshold": 0.02040816326530612,
                },
            }
        ),
        encoding="utf-8",
    )


def _portable_score(artifact: dict[str, Any], values: list[float]) -> float:
    nodes = artifact["tree"]["nodes"]
    index = artifact["tree"]["root_node"]
    while nodes[index]["kind"] == "split":
        node = nodes[index]
        index = (
            node["left"] if values[node["feature_index"]] <= node["threshold"] else node["right"]
        )
    return float(nodes[index]["positive_score"])


def test_export_is_deterministic_and_matches_source_tree(tmp_path: Path) -> None:
    features = [
        [10.0, 20.0, 30.0],
        [20.0, 20.0, 30.0],
        [70.0, 20.0, 30.0],
        [80.0, 30.0, 30.0],
    ]
    target = [1, 1, 0, 1]
    model = DecisionTreeClassifier(max_depth=2, random_state=42).fit(features, target)
    source = tmp_path / "model.joblib"
    evaluation = tmp_path / "evaluation.json"
    joblib.dump(model, source)
    _evaluation(evaluation)

    outputs: list[bytes] = []
    for suffix in ("a", "b"):
        output = tmp_path / f"model-{suffix}.json"
        digest = tmp_path / f"model-{suffix}.sha256"
        artifact = export_portable_tree(
            joblib_path=source,
            evaluation_path=evaluation,
            output_path=output,
            digest_path=digest,
        )
        outputs.append(output.read_bytes())
        assert (
            digest.read_text(encoding="ascii").strip()
            == hashlib.sha256(output.read_bytes()).hexdigest()
        )
        for row, expected in zip(features, model.predict_proba(features)[:, 1], strict=True):
            assert _portable_score(artifact, row) == expected

    assert outputs[0] == outputs[1]


@pytest.mark.skipif(not LOCAL_JOBLIB.exists(), reason="trusted local AGM-022 Joblib is ignored")
def test_versioned_runtime_artifact_matches_trusted_local_joblib(tmp_path: Path) -> None:
    output = tmp_path / "baseline-v1.json"
    digest = tmp_path / "baseline-v1.sha256"

    export_portable_tree(
        joblib_path=LOCAL_JOBLIB,
        evaluation_path=EVALUATION,
        output_path=output,
        digest_path=digest,
    )

    assert output.read_bytes() == VERSIONED_MODEL.read_bytes()
    assert digest.read_bytes() == VERSIONED_DIGEST.read_bytes()
