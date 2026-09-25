"""Transport-independent inference domain types."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from PIL import Image


class Classification(StrEnum):
    NORMAL = "NORMAL"
    ANOMALY = "ANOMALY"


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    user_id: UUID


@dataclass(frozen=True, slots=True)
class ValidatedImage:
    content_type: str
    width: int
    height: int
    rgb_image: Image.Image


@dataclass(frozen=True, slots=True)
class ModelResult:
    classification: Classification
    anomaly_softmax_probability: float
    decision_threshold: float
    model_version: str
    preprocessing_version: str
    artifact_sha256: str
    dataset_fingerprint: str


@dataclass(frozen=True, slots=True)
class InferenceResult:
    inference_id: UUID
    correlation_id: UUID
    farm_id: UUID
    model: ModelResult
    completed_at: datetime


class ServiceError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.safe_message = message
