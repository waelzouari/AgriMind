.PHONY: bootstrap format lint typecheck test secrets repo-check check

bootstrap:
	python3 -m pip install -e "./edge[dev]"

format:
	python3 -m ruff format edge/src edge/tests scripts

lint:
	python3 -m ruff check edge/src edge/tests scripts

typecheck:
	python3 -m mypy edge/src scripts

test:
	python3 -m pytest edge/tests

secrets: # pragma: allowlist secret
	python3 scripts/check_secrets.py # pragma: allowlist secret

repo-check:
	python3 scripts/check_repository.py

check: lint typecheck test secrets repo-check
