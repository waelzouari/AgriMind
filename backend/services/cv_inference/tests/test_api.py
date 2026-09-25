from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from conftest import FARM, IDENTIFIER, OTHER_FARM, FakeModel
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, FormatChecker
from PIL import Image

from agrimind_cv_inference.application.service import InferenceService
from agrimind_cv_inference.domain.models import Classification
from agrimind_cv_inference.entrypoints.http import create_app

ROOT = Path(__file__).parents[4]


def png() -> bytes:
    stream = io.BytesIO()
    Image.new("RGB", (8, 8), (1, 2, 3)).save(stream, format="PNG")
    return stream.getvalue()


def post(client: TestClient, farm: object = FARM, **headers: str):
    merged = {
        "Authorization": "Bearer valid-token",
        "Content-Type": "image/png",
        **headers,
    }
    return client.post(f"/v1/farms/{farm}/cv-inferences", content=png(), headers=merged)


def validate_schema(name: str, payload: object) -> None:
    schema = json.loads((ROOT / "contracts/v1" / name).read_text(encoding="utf-8"))
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(payload)


def test_success_contract_has_only_visual_screening_fields(
    service: InferenceService,
) -> None:
    response = post(TestClient(create_app(service)))
    assert response.status_code == 200
    payload = response.json()
    validate_schema("cv-inference-response.schema.json", payload)
    assert payload["classification"] == "ANOMALY"
    assert payload["anomaly_softmax_probability"] == 0.8
    assert payload["inference_id"] == str(IDENTIFIER)
    assert not ({"confidence", "diagnosis", "disease", "treatment", "irrigation"} & payload.keys())


def test_normal_result_and_client_correlation_id(
    service: InferenceService, model: FakeModel
) -> None:
    model.classification = Classification.NORMAL
    model.score = 0.2
    correlation = "31313131-3131-4131-8131-313131313135"
    payload = post(TestClient(create_app(service)), **{"X-Correlation-ID": correlation}).json()
    assert payload["classification"] == "NORMAL"
    assert payload["correlation_id"] == correlation


@pytest.mark.parametrize(
    ("headers", "status", "code"),
    [
        ({"Content-Type": "image/png"}, 401, "authentication_required"),
        (
            {"Authorization": "Bearer wrong", "Content-Type": "image/png"},
            401,
            "invalid_token",
        ),
    ],
)
def test_authentication_failures_are_structured(
    service: InferenceService, headers: dict[str, str], status: int, code: str
) -> None:
    response = TestClient(create_app(service)).post(
        f"/v1/farms/{FARM}/cv-inferences", content=png(), headers=headers
    )
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    validate_schema("cv-inference-error.schema.json", response.json())


def test_cross_farm_and_malformed_farm_fail_without_enumeration(
    service: InferenceService,
) -> None:
    client = TestClient(create_app(service))
    denied = post(client, OTHER_FARM)
    assert denied.status_code == 404
    assert denied.json()["error"]["code"] == "farm_access_denied"
    malformed = post(client, "not-a-uuid")
    assert malformed.status_code == 400
    assert malformed.json()["error"]["code"] == "invalid_request"


def test_model_exceptions_and_invalid_scores_never_become_normal(
    service: InferenceService, model: FakeModel
) -> None:
    client = TestClient(create_app(service))
    model.error = RuntimeError("private internal path")
    failed = post(client)
    assert failed.status_code == 500
    assert failed.json()["error"]["code"] == "inference_failed"
    assert "private internal path" not in failed.text
    model.error = None
    model.score = float("nan")
    invalid = post(client)
    assert invalid.status_code == 500
    assert invalid.json()["error"]["code"] == "inference_failed"


def test_invalid_correlation_and_oversized_content_length_are_rejected(
    service: InferenceService,
) -> None:
    client = TestClient(create_app(service))
    invalid = post(client, **{"X-Correlation-ID": "bad"})
    assert invalid.status_code == 400
    oversized = client.post(
        f"/v1/farms/{FARM}/cv-inferences",
        content=b"x",
        headers={
            "Authorization": "Bearer valid-token",
            "Content-Type": "image/png",
            "Content-Length": str(8 * 1024 * 1024 + 1),
        },
    )
    assert oversized.status_code == 413
