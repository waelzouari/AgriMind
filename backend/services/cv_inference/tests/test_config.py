from __future__ import annotations

from pathlib import Path

import pytest

from agrimind_cv_inference.config import CvInferenceConfig


def environment() -> dict[str, str]:
    return {
        "AGRIMIND_CV_SUPABASE_URL": "https://example.supabase.co",
        "AGRIMIND_CV_SUPABASE_PUBLISHABLE_KEY": "public-test-placeholder",
        "AGRIMIND_CV_MODEL_METADATA": "/models/metadata.json",
        "AGRIMIND_CV_MODEL_ARTIFACT": "/models/model.pt",
    }


def test_configuration_uses_only_public_supabase_boundary() -> None:
    config = CvInferenceConfig.from_environment(environment())
    assert config.model_artifact == Path("/models/model.pt")
    assert "public-test-placeholder" not in repr(config)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("AGRIMIND_CV_SUPABASE_URL", "http://unsafe.test"),
        ("AGRIMIND_CV_MODEL_METADATA", "relative.json"),
        ("AGRIMIND_CV_MODEL_ARTIFACT", "relative.pt"),
        ("AGRIMIND_CV_HTTP_PORT", "0"),
    ],
)
def test_invalid_configuration_fails_closed(name: str, value: str) -> None:
    values = environment()
    values[name] = value
    with pytest.raises(ValueError):
        CvInferenceConfig.from_environment(values)
