"""Strict, network-free runtime artifact verification and MobileNetV2 loading."""

from __future__ import annotations

import hashlib
import importlib
import json
import math
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from jsonschema import Draft202012Validator, FormatChecker


class ModelLoadError(RuntimeError):
    pass


class ProbabilityModel(Protocol):
    def predict(self, tensor: Any) -> tuple[str, float]: ...


@dataclass(frozen=True, slots=True)
class RuntimeManifest:
    schema_version: int
    model_version: str
    architecture: str
    label_mapping: dict[str, int]
    preprocessing_version: str
    dataset_fingerprint: str
    split_fingerprint: str
    artifact_path: str
    artifact_size_bytes: int
    artifact_sha256: str
    decision_threshold: float
    validation_fingerprint: str


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_runtime_manifest(path: Path, schema_path: Path) -> RuntimeManifest:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ModelLoadError("runtime model metadata is unreadable") from error
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(raw),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        raise ModelLoadError("runtime model metadata is incompatible")
    try:
        return RuntimeManifest(**raw)
    except TypeError as error:
        raise ModelLoadError("runtime model metadata fields are incompatible") from error


def verify_artifact(manifest: RuntimeManifest, artifact: Path) -> None:
    if manifest.architecture != "mobilenet_v2":
        raise ModelLoadError("unsupported model architecture")
    if manifest.label_mapping != {"NORMAL": 0, "ANOMALY": 1}:
        raise ModelLoadError("incompatible model label mapping")
    if manifest.preprocessing_version != "agrimind-cv-mobilenet-v2-preprocessing-v1":
        raise ModelLoadError("incompatible preprocessing contract")
    if not artifact.is_file():
        raise ModelLoadError("model artifact is unavailable")
    if artifact.stat().st_size != manifest.artifact_size_bytes:
        raise ModelLoadError("model artifact size mismatch")
    if _digest(artifact) != manifest.artifact_sha256:
        raise ModelLoadError("model artifact checksum mismatch")


class TorchProbabilityModel:
    def __init__(self, model: Any, torch: Any, threshold: float) -> None:
        self._model = model
        self._torch = torch
        self._threshold = threshold

    def predict(self, tensor: Any) -> tuple[str, float]:
        try:
            with self._torch.no_grad():
                output = self._model(tensor)
                if tuple(output.shape) != (1, 2):
                    raise ModelLoadError("model output shape is invalid")
                score = float(self._torch.softmax(output, dim=1)[0, 1].item())
        except ModelLoadError:
            raise
        except Exception as error:
            raise ModelLoadError("model inference failed") from error
        if not math.isfinite(score) or not 0.0 <= score <= 1.0:
            raise ModelLoadError("model output probability is invalid")
        return ("ANOMALY" if score >= self._threshold else "NORMAL", score)


def load_mobilenet_v2(
    manifest: RuntimeManifest,
    artifact: Path,
    *,
    runtime_loader: Callable[[], tuple[Any, Any]] | None = None,
) -> TorchProbabilityModel:
    verify_artifact(manifest, artifact)
    try:
        torch, torchvision = (
            runtime_loader()
            if runtime_loader is not None
            else (importlib.import_module("torch"), importlib.import_module("torchvision"))
        )
        model = torchvision.models.mobilenet_v2(weights=None)
        model.classifier[-1] = torch.nn.Linear(model.classifier[-1].in_features, 2)
        state = torch.load(artifact, map_location="cpu", weights_only=True)
        model.load_state_dict(state, strict=True)
        model.eval()
        output = model(torch.zeros((1, 3, 224, 224), dtype=torch.float32))
        if tuple(output.shape) != (1, 2):
            raise ModelLoadError("model self-check output shape is invalid")
        return TorchProbabilityModel(model, torch, manifest.decision_threshold)
    except ModelLoadError:
        raise
    except Exception as error:
        raise ModelLoadError("model artifact cannot be loaded") from error
