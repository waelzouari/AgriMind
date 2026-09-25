"""Secured, transport-independent inference orchestration."""

from __future__ import annotations

import logging
import math
from uuid import UUID

from agrimind_cv_inference.application.ports import (
    AuthenticationPort,
    Clock,
    FarmAuthorizationPort,
    IdentifierFactory,
    ImageValidationPort,
    ModelInferencePort,
)
from agrimind_cv_inference.domain.models import InferenceResult, ServiceError


class InferenceService:
    def __init__(
        self,
        authentication: AuthenticationPort,
        authorization: FarmAuthorizationPort,
        images: ImageValidationPort,
        model: ModelInferencePort,
        clock: Clock,
        identifiers: IdentifierFactory,
    ) -> None:
        self._authentication = authentication
        self._authorization = authorization
        self._images = images
        self._model = model
        self._clock = clock
        self._identifiers = identifiers

    def infer(
        self,
        *,
        farm_id: UUID,
        access_token: str,
        content_type: str,
        body: bytes,
        correlation_id: UUID | None,
    ) -> InferenceResult:
        user = self._authentication.authenticate(access_token)
        if not self._authorization.is_member(user, farm_id, access_token):
            raise ServiceError("farm_access_denied", "Farm is unavailable")
        image = self._images.validate(body, content_type)
        try:
            result = self._model.predict(image)
        except ServiceError:
            raise
        except Exception as error:
            raise ServiceError("inference_failed", "Inference failed") from error
        if (
            not math.isfinite(result.anomaly_softmax_probability)
            or not 0 <= result.anomaly_softmax_probability <= 1
            or result.classification.value not in {"NORMAL", "ANOMALY"}
        ):
            raise ServiceError("inference_failed", "Inference failed")
        inference_id = self._identifiers.new()
        correlated = correlation_id or inference_id
        logging.getLogger(__name__).info(
            "cv_inference result=completed inference_id=%s correlation_id=%s model=%s",
            inference_id,
            correlated,
            result.model_version,
        )
        return InferenceResult(
            inference_id,
            correlated,
            farm_id,
            result,
            self._clock.now(),
        )
