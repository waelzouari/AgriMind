"""Build and run the secured CV API after strict model readiness checks."""

from __future__ import annotations

import argparse
import importlib
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import uvicorn
from agrimind_cv.model_loading import load_mobilenet_v2, load_runtime_manifest
from dotenv import dotenv_values

from agrimind_cv_inference.adapters.images import PillowImageValidator
from agrimind_cv_inference.adapters.model import AgrimindCvModelAdapter
from agrimind_cv_inference.adapters.supabase import SupabaseUserBoundary
from agrimind_cv_inference.application.service import InferenceService
from agrimind_cv_inference.config import CvInferenceConfig
from agrimind_cv_inference.entrypoints.http import create_app

ROOT = Path(__file__).resolve().parents[6]
SCHEMA = ROOT / "ai/computer_vision/data_contracts/runtime-model.v1.schema.json"


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class UuidFactory:
    def new(self) -> UUID:
        return uuid4()


def _environment(path: Path) -> dict[str, str]:
    values = {key: value for key, value in dotenv_values(path).items() if value is not None}
    values.update(os.environ)
    return values


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    args = parser.parse_args(arguments)
    config = CvInferenceConfig.from_environment(_environment(args.env_file))
    manifest = load_runtime_manifest(config.model_metadata, SCHEMA)
    model = load_mobilenet_v2(manifest, config.model_artifact)
    torch = importlib.import_module("torch")
    supabase = SupabaseUserBoundary(
        config.supabase_url,
        config.supabase_publishable_key.value,
        timeout_seconds=config.http_timeout_seconds,
    )
    service = InferenceService(
        supabase,
        supabase,
        PillowImageValidator(),
        AgrimindCvModelAdapter(model, manifest, torch),
        SystemClock(),
        UuidFactory(),
    )
    uvicorn.run(create_app(service), host=config.http_host, port=config.http_port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
