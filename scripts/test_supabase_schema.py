"""Validate Supabase migrations on disposable PostgreSQL databases."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "backend/supabase/tests/bootstrap_auth.sql"
AGM_010_MIGRATION = (
    ROOT / "backend/supabase/migrations/20260923140000_agm_010_initial_schema.sql"
)
AGM_010_TESTS = ROOT / "backend/supabase/tests/agm_010_schema_test.sql"
AGM_011_MIGRATION = (
    ROOT / "backend/supabase/migrations/20260923150000_agm_011_auth_rls.sql"
)
AGM_011_TESTS = ROOT / "backend/supabase/tests/agm_011_rls_test.sql"
AGM_012_MIGRATION = (
    ROOT / "backend/supabase/migrations/20260923160000_agm_012_secure_ingestion.sql"
)
AGM_012_TESTS = ROOT / "backend/supabase/tests/agm_012_ingestion_test.sql"


def _run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def run_clean_database() -> None:
    database = f"agrimind_schema_{uuid4().hex}"
    _run(["createdb", database])
    try:
        # AGM-010 tests its pre-RLS contract before the additive AGM-011
        # security migration is applied.
        for sql_file in (
            BOOTSTRAP,
            AGM_010_MIGRATION,
            AGM_010_TESTS,
            AGM_011_MIGRATION,
            AGM_011_TESTS,
            AGM_012_MIGRATION,
            AGM_012_TESTS,
        ):
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
        "AGM-010/011/012 schema, RLS, and trusted ingestion tests passed "
        "twice from clean state."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
