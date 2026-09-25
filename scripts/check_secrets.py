"""Fail when detect-secrets reports a candidate in repository-owned files."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import TypedDict, cast

ROOT = Path(__file__).resolve().parents[1]


class ScanResult(TypedDict):
    results: dict[str, list[object]]


def main() -> int:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "detect_secrets",
            "scan",
            "--exclude-files",
            r"^\.venv/",
            "--exclude-files",
            r"^\.git/",
            "--exclude-lines",
            r'"(?:dataset_sha256|dataset_version|source_revision|sha256)"',
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    scan = cast(ScanResult, json.loads(completed.stdout))
    findings = scan["results"]
    if findings:
        for filename, candidates in sorted(findings.items()):
            print(f"ERROR: {filename} contains {len(candidates)} secret candidate(s)")
        return 1
    print("Secret scan passed with no candidates.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
