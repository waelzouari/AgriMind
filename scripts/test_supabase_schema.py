"""Execute AGM-010 migrations and constraints on disposable PostgreSQL databases."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "backend/supabase/tests/bootstrap_auth.sql"
MIGRATION = (
    ROOT / "backend/supabase/migrations/20260923140000_agm_010_initial_schema.sql"
)
TESTS = ROOT / "backend/supabase/tests/agm_010_schema_test.sql"


def _run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def run_clean_database() -> None:
    database = f"agrimind_agm010_{uuid4().hex}"
    _run(["createdb", database])
    try:
        for sql_file in (BOOTSTRAP, MIGRATION, TESTS):
            _run(
                [
                    "psql",
                    "--set",
                    "ON_ERROR_STOP=1",
                    "--dbname",
                    database,
                    "--file",
                    str(sql_file),
                ]
            )
    finally:
        _run(["dropdb", "--if-exists", database])


def main() -> int:
    missing = [
        tool for tool in ("createdb", "psql", "dropdb") if shutil.which(tool) is None
    ]
    if missing:
        raise RuntimeError(f"missing PostgreSQL tools: {', '.join(missing)}")
    run_clean_database()
    run_clean_database()
    print(
        "AGM-010 schema migration and constraint tests passed twice from clean state."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
