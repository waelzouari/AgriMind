"""Adapter from validated Pillow images to the versioned agrimind_cv runtime."""

from __future__ import annotations

from typing import Any

import numpy as np
from agrimind_cv.model_loading import RuntimeManifest, TorchProbabilityModel
from agrimind_cv.preprocessing import PreprocessingContract, preprocess_evaluation

from agrimind_cv_inference.domain.models import (
    Classification,
    ModelResult,
    ServiceError,
    ValidatedImage,
)


class AgrimindCvModelAdapter:
    def __init__(self, model: TorchProbabilityModel, manifest: RuntimeManifest, torch: Any) -> None:
        self._model = model
        self._manifest = manifest
        self._torch = torch
        self._preprocessing = PreprocessingContract()

    def predict(self, image: ValidatedImage) -> ModelResult:
        try:
            array = preprocess_evaluation(image.rgb_image, self._preprocessing)
            tensor = self._torch.from_numpy(np.expand_dims(array, 0))
            classification, score = self._model.predict(tensor)
            return ModelResult(
                Classification(classification),
                score,
                self._manifest.decision_threshold,
                self._manifest.model_version,
                self._manifest.preprocessing_version,
                self._manifest.artifact_sha256,
                self._manifest.dataset_fingerprint,
            )
        except (ValueError, RuntimeError) as error:
            raise ServiceError("inference_failed", "Inference failed") from error
