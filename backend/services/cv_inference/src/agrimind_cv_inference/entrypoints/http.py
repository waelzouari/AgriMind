"""FastAPI transport for the stable AGM-031 inference contract."""

from __future__ import annotations

from datetime import UTC
from uuid import UUID, uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from agrimind_cv_inference.adapters.images import MAX_BODY_BYTES
from agrimind_cv_inference.application.service import InferenceService
from agrimind_cv_inference.domain.models import ServiceError


def _error(status: int, code: str, message: str, correlation_id: UUID) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={
            "schema_version": 1,
            "error": {
                "code": code,
                "correlation_id": str(correlation_id),
                "message": message,
            },
        },
    )


def _status(code: str) -> int:
    return {
        "authentication_required": 401,
        "invalid_token": 401,
        "farm_access_denied": 404,
        "invalid_request": 400,
        "unsupported_image_type": 415,
        "image_too_large": 413,
        "invalid_image": 400,
        "unsupported_image_dimensions": 422,
        "model_unavailable": 503,
        "inference_failed": 500,
    }.get(code, 500)


async def _bounded_body(request: Request) -> bytes:
    declared = request.headers.get("content-length")
    if declared is not None:
        try:
            if int(declared) > MAX_BODY_BYTES:
                raise ServiceError("image_too_large", "Image exceeds the encoded size limit")
        except ValueError as error:
            raise ServiceError("invalid_request", "Content-Length is invalid") from error
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_BODY_BYTES:
            raise ServiceError("image_too_large", "Image exceeds the encoded size limit")
    return bytes(body)


def create_app(service: InferenceService) -> FastAPI:
    app = FastAPI(title="AgriMind CV inference", version="1")

    @app.get("/health/ready")
    def readiness() -> dict[str, str]:
        return {"status": "ready"}

    @app.post("/v1/farms/{farm_id}/cv-inferences")
    async def infer(farm_id: str, request: Request) -> JSONResponse:
        generated = uuid4()
        correlation_header = request.headers.get("x-correlation-id")
        try:
            correlation_id = UUID(correlation_header) if correlation_header else generated
            requested_farm = UUID(farm_id)
        except ValueError:
            return _error(400, "invalid_request", "Request identifier is invalid", generated)
        authorization = request.headers.get("authorization", "")
        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1]:
            return _error(
                401,
                "authentication_required",
                "Authentication is required",
                correlation_id,
            )
        try:
            result = service.infer(
                farm_id=requested_farm,
                access_token=parts[1],
                content_type=request.headers.get("content-type", ""),
                body=await _bounded_body(request),
                correlation_id=correlation_id,
            )
        except ServiceError as error:
            return _error(_status(error.code), error.code, error.safe_message, correlation_id)
        model = result.model
        completed = result.completed_at.astimezone(UTC).isoformat().replace("+00:00", "Z")
        return JSONResponse(
            {
                "schema_version": 1,
                "inference_id": str(result.inference_id),
                "correlation_id": str(result.correlation_id),
                "farm_id": str(result.farm_id),
                "classification": model.classification.value,
                "anomaly_softmax_probability": model.anomaly_softmax_probability,
                "decision_threshold": model.decision_threshold,
                "model_version": model.model_version,
                "preprocessing_version": model.preprocessing_version,
                "artifact_sha256": model.artifact_sha256,
                "dataset_fingerprint": model.dataset_fingerprint,
                "completed_at": completed,
            }
        )

    return app
