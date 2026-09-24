.PHONY: bootstrap format lint typecheck test backend-format backend-lint backend-typecheck backend-test db-test secrets repo-check check

bootstrap:
	python3 -m pip install -e "./edge[dev]"
	python3 -m pip install -e "./backend/services/ingestion[dev]"
	python3 -m pip install -e "./backend/services/weather[dev]"

format:
	python3 -m ruff format edge/src edge/tests scripts
	python3 -m ruff format backend/services/ingestion/src backend/services/ingestion/tests
	python3 -m ruff format backend/services/weather/src backend/services/weather/tests

lint:
	python3 -m ruff check edge/src edge/tests scripts

backend-format:
	python3 -m ruff format --check backend/services/ingestion/src backend/services/ingestion/tests
	python3 -m ruff format --check backend/services/weather/src backend/services/weather/tests

backend-lint:
	python3 -m ruff check backend/services/ingestion/src backend/services/ingestion/tests
	python3 -m ruff check backend/services/weather/src backend/services/weather/tests

backend-typecheck:
	python3 -m mypy --config-file backend/services/ingestion/pyproject.toml backend/services/ingestion/src
	python3 -m mypy --config-file backend/services/weather/pyproject.toml backend/services/weather/src

backend-test:
	python3 -m pytest -q backend/services/ingestion/tests
	python3 -m pytest -q backend/services/weather/tests

typecheck:
	python3 -m mypy edge/src scripts

test:
	python3 -m pytest edge/tests

db-test:
	python3 scripts/test_supabase_schema.py

secrets: # pragma: allowlist secret
	python3 scripts/check_secrets.py # pragma: allowlist secret

repo-check:
	python3 scripts/check_repository.py

check: lint typecheck test backend-format backend-lint backend-typecheck backend-test secrets repo-check
