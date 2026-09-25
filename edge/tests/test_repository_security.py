from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from scripts.check_repository import validate_tracked_paths


def _repository(tmp_path: Path, tracked_path: str) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    target = tmp_path / tracked_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("safe deterministic fixture\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "-f", tracked_path], check=True)
    return tmp_path


@pytest.mark.parametrize(
    ("path", "reason"),
    [
        (".env", "real environment file"),
        (".secrets/mobile.env", "local secrets directory"),
        ("deploy/device.key", "private key or certificate"),
        ("runtime/edge.sqlite3", "runtime database"),
        ("ai/irrigation/artifacts/baseline-v1.joblib", "generated model artifact"),
        ("ai/irrigation/data/raw/source.csv", "raw or generated AI dataset"),
    ],
)
def test_tracked_sensitive_paths_are_rejected(tmp_path: Path, path: str, reason: str) -> None:
    root = _repository(tmp_path, path)

    assert validate_tracked_paths(root) == [f"tracked sensitive path ({reason}): {path}"]


@pytest.mark.parametrize(
    "path",
    [
        ".env.example",
        "backend/services/ingestion/.env.example",
        "deploy/mosquitto/agrimind-device.acl.example",
        "edge/src/agrimind_edge/application/service.py",
        "ai/irrigation/artifacts/.gitkeep",
    ],
)
def test_safe_examples_and_source_files_are_allowed(tmp_path: Path, path: str) -> None:
    root = _repository(tmp_path, path)

    assert validate_tracked_paths(root) == []
