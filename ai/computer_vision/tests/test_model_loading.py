from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from agrimind_cv.model_loading import (
    ModelLoadError,
    RuntimeManifest,
    TorchProbabilityModel,
    load_mobilenet_v2,
    load_runtime_manifest,
    verify_artifact,
)

SCHEMA = Path(__file__).parents[1] / "data_contracts" / "runtime-model.v1.schema.json"


def manifest(artifact: Path) -> dict[str, object]:
    content = artifact.read_bytes()
    return {
        "schema_version": 1,
        "model_version": "1.0.0",
        "architecture": "mobilenet_v2",
        "label_mapping": {"NORMAL": 0, "ANOMALY": 1},
        "preprocessing_version": "agrimind-cv-mobilenet-v2-preprocessing-v1",
        "dataset_fingerprint": "d" * 64,
        "split_fingerprint": "b" * 64,
        "artifact_path": "external/model.pt",
        "artifact_size_bytes": len(content),
        "artifact_sha256": hashlib.sha256(content).hexdigest(),
        "decision_threshold": 0.5,
        "validation_fingerprint": "c" * 64,
    }


def load(tmp_path: Path, payload: dict[str, object]) -> RuntimeManifest:
    path = tmp_path / "metadata.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return load_runtime_manifest(path, SCHEMA)


def test_runtime_manifest_and_artifact_are_strictly_verified(tmp_path: Path) -> None:
    artifact = tmp_path / "model.pt"
    artifact.write_bytes(b"trusted-test-artifact")
    parsed = load(tmp_path, manifest(artifact))
    verify_artifact(parsed, artifact)


def test_missing_and_corrupt_artifact_fail_closed(tmp_path: Path) -> None:
    artifact = tmp_path / "model.pt"
    artifact.write_bytes(b"trusted-test-artifact")
    parsed = load(tmp_path, manifest(artifact))
    artifact.unlink()
    with pytest.raises(ModelLoadError, match="unavailable"):
        verify_artifact(parsed, artifact)
    artifact.write_bytes(b"different")
    with pytest.raises(ModelLoadError, match="size mismatch"):
        verify_artifact(parsed, artifact)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("architecture", "resnet"),
        ("label_mapping", {"NORMAL": 1, "ANOMALY": 0}),
        ("preprocessing_version", "other"),
        ("decision_threshold", 2),
    ],
)
def test_incompatible_metadata_is_rejected(tmp_path: Path, field: str, value: object) -> None:
    artifact = tmp_path / "model.pt"
    artifact.write_bytes(b"model")
    payload = manifest(artifact)
    payload[field] = value
    with pytest.raises(ModelLoadError, match="incompatible"):
        load(tmp_path, payload)


class _Context:
    def __enter__(self) -> None:
        return None

    def __exit__(self, *args: object) -> None:
        return None


class _Scalar:
    def __init__(self, value: float) -> None:
        self.value = value

    def item(self) -> float:
        return self.value


class _Output:
    def __init__(self, value: float, shape: tuple[int, ...] = (1, 2)) -> None:
        self.value = value
        self.shape = shape

    def __getitem__(self, key: object) -> _Scalar:
        del key
        return _Scalar(self.value)


class _Linear:
    def __init__(self, incoming: int, outgoing: int) -> None:
        self.in_features = incoming
        self.outgoing = outgoing


class _Model:
    def __init__(self, output: _Output | Exception) -> None:
        self.output = output
        self.loaded: tuple[object, bool] | None = None
        self.classifier = [_Linear(1, 2)]

    def __call__(self, tensor: object) -> _Output:
        del tensor
        if isinstance(self.output, Exception):
            raise self.output
        return self.output

    def load_state_dict(self, state: object, *, strict: bool) -> None:
        self.loaded = (state, strict)

    def eval(self) -> None:
        return None


class _Torch:
    float32 = "float32"

    class nn:
        Linear = _Linear

    def __init__(self, softmax_value: float = 0.8) -> None:
        self.softmax_value = softmax_value

    def no_grad(self) -> _Context:
        return _Context()

    def softmax(self, output: _Output, *, dim: int) -> _Output:
        del output, dim
        return _Output(self.softmax_value)

    def load(self, path: Path, *, map_location: str, weights_only: bool) -> dict[str, int]:
        del path, map_location, weights_only
        return {"weight": 1}

    def zeros(self, shape: tuple[int, ...], *, dtype: str) -> object:
        del shape, dtype
        return object()


class _Models:
    def __init__(self, model: _Model) -> None:
        self.model = model
        self.weights_argument: object = "not-called"

    def mobilenet_v2(self, *, weights: object) -> _Model:
        self.weights_argument = weights
        return self.model


class _Vision:
    def __init__(self, model: _Model) -> None:
        self.models = _Models(model)


def test_loader_never_requests_network_weights_and_loads_strictly(tmp_path: Path) -> None:
    artifact = tmp_path / "model.pt"
    artifact.write_bytes(b"model")
    parsed = load(tmp_path, manifest(artifact))
    model = _Model(_Output(0.0))
    torch, vision = _Torch(), _Vision(model)
    loaded = load_mobilenet_v2(parsed, artifact, runtime_loader=lambda: (torch, vision))
    assert loaded is not None
    assert vision.models.weights_argument is None
    assert model.loaded == ({"weight": 1}, True)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -0.1, 1.1])
def test_probability_model_rejects_invalid_scores(value: float) -> None:
    model = TorchProbabilityModel(_Model(_Output(0.0)), _Torch(value), 0.5)
    with pytest.raises(ModelLoadError, match="probability"):
        model.predict(object())


def test_probability_model_threshold_output_shape_and_exception() -> None:
    assert TorchProbabilityModel(_Model(_Output(0.0)), _Torch(0.5), 0.5).predict(object()) == (
        "ANOMALY",
        0.5,
    )
    with pytest.raises(ModelLoadError, match="shape"):
        TorchProbabilityModel(_Model(_Output(0.0, (1, 3))), _Torch(), 0.5).predict(object())
    with pytest.raises(ModelLoadError, match="failed"):
        TorchProbabilityModel(_Model(RuntimeError("boom")), _Torch(), 0.5).predict(object())
