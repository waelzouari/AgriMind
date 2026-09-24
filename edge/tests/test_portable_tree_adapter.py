from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from agrimind_edge.adapters.ml import PortableTreeModelAdapter
from agrimind_edge.application.inference_ports import (
    ArtifactIntegrityError,
    ModelCompatibilityError,
    ModelUnavailableError,
)
from agrimind_edge.domain import IrrigationFeatureVector

ROOT = Path(__file__).parents[1]
MODEL = ROOT / "src/agrimind_edge/adapters/ml/models/baseline-v1.json"
DIGEST = ROOT / "src/agrimind_edge/adapters/ml/models/baseline-v1.sha256"


def _write_artifact(tmp_path: Path, update: Callable[[dict[str, Any]], None]) -> tuple[Path, Path]:
    raw = json.loads(MODEL.read_text(encoding="utf-8"))
    if callable(update):
        update(raw)
    encoded = (json.dumps(raw, indent=2, sort_keys=True) + "\n").encode()
    artifact = tmp_path / "model.json"
    digest = tmp_path / "model.sha256"
    artifact.write_bytes(encoded)
    digest.write_text(f"{hashlib.sha256(encoded).hexdigest()}\n", encoding="ascii")
    return artifact, digest


@pytest.mark.parametrize(
    ("features", "score"),
    [
        ((30.0, 20.0, 60.0), 0.02040816326530612),
        ((45.0, 20.0, 60.0), 0.94),
        ((60.0, 20.0, 60.0), 0.0028694404591104736),
        ((60.0, 25.0, 60.0), 0.5806451612903226),
    ],
)
def test_packaged_tree_reproduces_all_four_leaf_scores(
    features: tuple[float, float, float], score: float
) -> None:
    prediction = PortableTreeModelAdapter().predict(IrrigationFeatureVector(*features))

    assert prediction.score == score
    assert prediction.model_version == "irrigation-baseline-v1"
    assert prediction.feature_contract_version == "v1"


def test_missing_artifact_is_explicit(tmp_path: Path) -> None:
    adapter = PortableTreeModelAdapter(tmp_path / "missing.json", tmp_path / "missing.sha256")

    with pytest.raises(ModelUnavailableError):
        adapter.predict(IrrigationFeatureVector(45.0, 25.0, 60.0))


def test_modified_bytes_fail_integrity(tmp_path: Path) -> None:
    artifact = tmp_path / "model.json"
    digest = tmp_path / "model.sha256"
    artifact.write_bytes(MODEL.read_bytes() + b" ")
    digest.write_bytes(DIGEST.read_bytes())

    with pytest.raises(ArtifactIntegrityError):
        PortableTreeModelAdapter(artifact, digest).predict(
            IrrigationFeatureVector(45.0, 25.0, 60.0)
        )


@pytest.mark.parametrize(
    "update",
    [
        lambda raw: raw.update(artifact_version="v2"),
        lambda raw: raw.update(model_version="other"),
        lambda raw: raw.update(feature_contract_version="v2"),
        lambda raw: raw.update(methodology_version="other"),
        lambda raw: raw.update(dataset_sha256="0" * 64),
        lambda raw: raw.update(decision_threshold=0.5),
        lambda raw: raw.update(ordered_features=list(reversed(raw["ordered_features"]))),
        lambda raw: raw.update(target_classes=[1, 0]),
    ],
)
def test_incompatible_metadata_is_rejected(
    tmp_path: Path, update: Callable[[dict[str, Any]], None]
) -> None:
    artifact, digest = _write_artifact(tmp_path, update)

    with pytest.raises(ModelCompatibilityError):
        PortableTreeModelAdapter(artifact, digest).predict(
            IrrigationFeatureVector(45.0, 25.0, 60.0)
        )


def test_corrupt_json_with_valid_digest_is_rejected(tmp_path: Path) -> None:
    encoded = b"{not-json}\n"
    artifact = tmp_path / "model.json"
    digest = tmp_path / "model.sha256"
    artifact.write_bytes(encoded)
    digest.write_text(hashlib.sha256(encoded).hexdigest(), encoding="ascii")

    with pytest.raises(ModelCompatibilityError):
        PortableTreeModelAdapter(artifact, digest).predict(
            IrrigationFeatureVector(45.0, 25.0, 60.0)
        )


def test_adapter_loads_only_once(tmp_path: Path) -> None:
    artifact, digest = _write_artifact(tmp_path, lambda raw: None)
    adapter = PortableTreeModelAdapter(artifact, digest)
    features = IrrigationFeatureVector(45.0, 25.0, 60.0)

    first = adapter.predict(features)
    artifact.unlink()
    digest.unlink()
    second = adapter.predict(features)

    assert first == second
