.PHONY: bootstrap format lint typecheck test cv-test db-test secrets repo-check check

bootstrap:
	python3 -m pip install -e "./edge[dev]"
	python3 -m pip install -e "./ai/computer_vision[dev]"

format:
	python3 -m ruff format edge/src edge/tests ai/computer_vision/src ai/computer_vision/tests scripts

lint:
	python3 -m ruff check edge/src edge/tests ai/computer_vision/src ai/computer_vision/tests scripts

typecheck:
	python3 -m mypy edge/src scripts
	python3 -m mypy --config-file ai/computer_vision/pyproject.toml ai/computer_vision/src

test:
	python3 -m pytest edge/tests

cv-test:
	python3 -m pytest -c ai/computer_vision/pyproject.toml ai/computer_vision/tests

db-test:
	python3 scripts/test_supabase_schema.py

secrets: # pragma: allowlist secret
	python3 scripts/check_secrets.py # pragma: allowlist secret

repo-check:
	python3 scripts/check_repository.py

check: lint typecheck test cv-test secrets repo-check
