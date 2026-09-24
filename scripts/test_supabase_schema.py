"""Validate Supabase migrations on disposable PostgreSQL databases."""

from __future__ import annotations

import shutil
import subprocess
import time
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
AGM_016_MIGRATION = (
    ROOT / "backend/supabase/migrations/20260923170000_agm_016_one_farm_onboarding.sql"
)
AGM_016_TESTS = ROOT / "backend/supabase/tests/agm_016_onboarding_test.sql"
AGM_019_MIGRATION = (
    ROOT / "backend/supabase/migrations/20260923180000_agm_019_weather.sql"
)
AGM_019_TESTS = ROOT / "backend/supabase/tests/agm_019_weather_test.sql"
AGM_028_MIGRATION = (
    ROOT / "backend/supabase/migrations/20260924100000_agm_028_farm_manager.sql"
)
AGM_028_TESTS = ROOT / "backend/supabase/tests/agm_028_farm_manager_test.sql"
AGM_025_MIGRATION = (
    ROOT / "backend/supabase/migrations/20260924190000_agm_025_irrigation_feedback.sql"
)
AGM_025_TESTS = ROOT / "backend/supabase/tests/agm_025_irrigation_feedback_test.sql"


def _run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def _run_onboarding_concurrency_test(database: str) -> None:
    user_id = "16161616-1616-4616-8616-161616161616"
    _run(
        [
            "psql",
            "--set",
            "ON_ERROR_STOP=1",
            "--dbname",
            database,
            "--command",
            f"insert into auth.users(id) values ('{user_id}')",
        ]
    )
    call = (
        "begin; "
        "set local role authenticated; "
        f"select set_config('request.jwt.claim.sub', '{user_id}', true); "
        "select id from public.create_farm_for_current_user('Concurrent farm'); "
        "select pg_sleep(1); "
        "commit;"
    )
    first = subprocess.Popen(
        ["psql", "--set", "ON_ERROR_STOP=1", "--dbname", database, "--command", call],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    time.sleep(0.2)
    second = subprocess.run(
        ["psql", "--set", "ON_ERROR_STOP=1", "--dbname", database, "--command", call],
        check=False,
        capture_output=True,
        text=True,
    )
    first_stdout, first_stderr = first.communicate(timeout=10)
    if first.returncode != 0:
        raise RuntimeError(first_stderr or first_stdout)
    if second.returncode != 0:
        raise RuntimeError(second.stderr or second.stdout)

    result = subprocess.run(
        [
            "psql",
            "--tuples-only",
            "--no-align",
            "--dbname",
            database,
            "--command",
            (
                "select count(*), count(distinct farm_id) "
                "from public.farm_memberships "
                f"where user_id = '{user_id}' and role = 'owner'"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if result != "1|1":
        raise RuntimeError(
            f"concurrent onboarding created unexpected memberships: {result}"
        )


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
            AGM_016_MIGRATION,
            AGM_016_TESTS,
            AGM_019_MIGRATION,
            AGM_019_TESTS,
            AGM_028_MIGRATION,
            AGM_028_TESTS,
            AGM_025_MIGRATION,
            AGM_025_TESTS,
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
        _run_onboarding_concurrency_test(database)
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
        "AGM-010/011/012/016/019/028/025 schema, RLS, ingestion, onboarding, weather, farm manager, and irrigation feedback tests passed "
        "twice from clean state."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
