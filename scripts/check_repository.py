"""Validate repository-foundation invariants without external services."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_PATHS = (
    ".env.example",
    ".github/workflows/foundation.yml",
    "backend/supabase/migrations/README.md",
    "contracts/v1/telemetry.schema.json",
    "contracts/v1/pump-command.schema.json",
    "contracts/v1/command-acknowledgement.schema.json",
    "contracts/v1/device-status.schema.json",
    "contracts/v1/irrigation-result.schema.json",
    "contracts/v1/ingestion-acknowledgement.schema.json",
    "contracts/README.md",
    "docs/adrs/ADR-001-monorepo-and-boundaries.md",
    "docs/configuration.md",
    "docs/mqtt/topics.md",
    "edge/pyproject.toml",
    "ai/computer_vision/pyproject.toml",
    "ai/computer_vision/configs/datasets/plantvillage-notebook-mirror-v1.json",
    "ai/computer_vision/configs/evaluation/mobilenet-v2-v1.json",
    "ai/computer_vision/data_contracts/artifact-metadata.v2.schema.json",
    "ai/computer_vision/data_contracts/official-evaluation.v1.schema.json",
    "ai/computer_vision/data_contracts/runtime-model.v1.schema.json",
    "ai/computer_vision/notebooks/AGM_031_Official_Evaluation_Colab.ipynb",
    "ai/computer_vision/README.md",
    "backend/services/cv_inference/pyproject.toml",
    "contracts/v1/cv-inference-response.schema.json",
    "contracts/v1/cv-inference-error.schema.json",
    "mobile/README.md",
)
FORBIDDEN_ENV_NAMES = ("SERVICE_ROLE", "PRIVATE_KEY")
PLACEHOLDER_MARKERS = ("replace-at-deployment", "replace-with-public-anon-key")


def _sensitive_tracked_path_reason(path: str) -> str | None:
    candidate = Path(path)
    name = candidate.name.lower()
    parts = tuple(part.lower() for part in candidate.parts)

    if name == ".env" or (name.startswith(".env.") and not name.endswith(".example")):
        return "real environment file"
    if ".secrets" in parts:
        return "local secrets directory"
    if candidate.suffix.lower() in {".pem", ".key", ".p12", ".pfx"}:
        return "private key or certificate"
    if candidate.suffix.lower() in {".db", ".sqlite", ".sqlite3"}:
        return "runtime database"
    if candidate.suffix.lower() == ".passwd":
        return "runtime password file"
    if candidate.suffix.lower() == ".acl" and not name.endswith(".acl.example"):
        return "runtime ACL file"
    if candidate.suffix.lower() in {".joblib", ".pkl", ".onnx", ".pt", ".pth"}:
        return "generated model artifact"
    if (
        len(parts) >= 4
        and parts[0] == "ai"
        and parts[2:4] in {("data", "raw"), ("data", "interim"), ("data", "processed")}
        and name != ".gitkeep"
    ):
        return "raw or generated AI dataset"
    return None


def validate_tracked_paths(root: Path = ROOT) -> list[str]:
    completed = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        check=True,
        capture_output=True,
        text=True,
    )
    errors: list[str] = []
    for path in completed.stdout.split("\0"):
        if not path:
            continue
        reason = _sensitive_tracked_path_reason(path)
        if reason is not None:
            errors.append(f"tracked sensitive path ({reason}): {path}")
    return errors


def validate_required_paths() -> list[str]:
    return [path for path in REQUIRED_PATHS if not (ROOT / path).exists()]


def validate_environment_example(path: Path | None = None) -> list[str]:
    content = (path or ROOT / ".env.example").read_text(encoding="utf-8")
    errors = [
        f"forbidden variable name in .env.example: {name}"
        for name in FORBIDDEN_ENV_NAMES
        if name in content
    ]
    if not all(marker in content for marker in PLACEHOLDER_MARKERS):
        errors.append(".env.example must use explicit non-secret placeholders")
    return errors


def validate_relative_markdown_links(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    pattern = re.compile(r"\[[^]]+\]\((?!https?://|#|mailto:)([^)]+)\)")
    for document in root.rglob("*.md"):
        if ".git" in document.parts:
            continue
        for target in pattern.findall(document.read_text(encoding="utf-8")):
            clean_target = target.split("#", 1)[0]
            if clean_target and not (document.parent / clean_target).resolve().exists():
                errors.append(f"{document.relative_to(root)}: broken link {target}")
    return errors


def main() -> int:
    errors = [
        *validate_required_paths(),
        *validate_environment_example(),
        *validate_relative_markdown_links(),
        *validate_tracked_paths(),
    ]
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Repository foundation checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
