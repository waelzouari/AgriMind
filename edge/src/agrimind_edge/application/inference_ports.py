"""Application boundary for local irrigation model inference."""

from __future__ import annotations

from typing import Protocol

from agrimind_edge.domain.irrigation_inference import (
    IrrigationFeatureVector,
    ModelPrediction,
)


class ModelUnavailableError(Exception):
    """The configured artifact cannot be accessed."""


class ArtifactIntegrityError(Exception):
    """The artifact bytes do not match their deterministic digest."""


class ModelCompatibilityError(Exception):
    """The artifact does not implement the approved V1 model contract."""


class ModelInferenceError(Exception):
    """The compatible model could not produce a score."""


class IrrigationModelPort(Protocol):
    def predict(self, features: IrrigationFeatureVector) -> ModelPrediction: ...
