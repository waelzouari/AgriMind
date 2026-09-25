.PHONY: bootstrap format lint typecheck test backend-format backend-lint backend-typecheck backend-test cv-service-format cv-service-lint cv-service-typecheck cv-service-test ai-format ai-lint ai-typecheck ai-test cv-format cv-lint cv-typecheck cv-test db-test secrets repo-check check

bootstrap:
	python3 -m pip install -e "./edge[dev]"
	python3 -m pip install -e "./backend/services/ingestion[dev]"
	python3 -m pip install -e "./backend/services/weather[dev]"
	python3 -m pip install -e "./ai/irrigation[dev]"
	python3 -m pip install -e "./ai/computer_vision[dev]"
	python3 -m pip install -e "./backend/services/cv_inference[dev]"

format:
	python3 -m ruff format edge/src edge/tests scripts
	python3 -m ruff format backend/services/ingestion/src backend/services/ingestion/tests
	python3 -m ruff format backend/services/weather/src backend/services/weather/tests
	python3 -m ruff format ai/irrigation/src ai/irrigation/tests

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

cv-service-format:
	python3 -m ruff format --check backend/services/cv_inference/src backend/services/cv_inference/tests

cv-service-lint:
	python3 -m ruff check backend/services/cv_inference/src backend/services/cv_inference/tests

cv-service-typecheck:
	python3 -m mypy --config-file backend/services/cv_inference/pyproject.toml backend/services/cv_inference/src

cv-service-test:
	python3 -m pytest -q -c backend/services/cv_inference/pyproject.toml backend/services/cv_inference/tests

ai-format:
	python3 -m ruff format --check ai/irrigation/src ai/irrigation/tests

ai-lint:
	python3 -m ruff check ai/irrigation/src ai/irrigation/tests

ai-typecheck:
	python3 -m mypy --config-file ai/irrigation/pyproject.toml ai/irrigation/src

ai-test:
	python3 -m pytest -q ai/irrigation/tests

cv-format:
	python3 -m ruff format --check ai/computer_vision/src ai/computer_vision/tests

cv-lint:
	python3 -m ruff check ai/computer_vision/src ai/computer_vision/tests

cv-typecheck:
	python3 -m mypy --config-file ai/computer_vision/pyproject.toml ai/computer_vision/src

cv-test:
	python3 -m pytest -q -c ai/computer_vision/pyproject.toml ai/computer_vision/tests

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

check: lint typecheck test backend-format backend-lint backend-typecheck backend-test cv-service-format cv-service-lint cv-service-typecheck cv-service-test ai-format ai-lint ai-typecheck ai-test cv-format cv-lint cv-typecheck cv-test secrets repo-check
