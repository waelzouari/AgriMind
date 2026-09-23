"""Validate repository-foundation invariants without external services."""

from __future__ import annotations

import re
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
    "mobile/README.md",
)
FORBIDDEN_ENV_NAMES = ("SERVICE_ROLE", "PRIVATE_KEY")
PLACEHOLDER_MARKERS = ("replace-at-deployment", "replace-with-public-anon-key")


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
    ]
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Repository foundation checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
