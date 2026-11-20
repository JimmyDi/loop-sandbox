.PHONY: setup install check specs package build up smoke mcp rotation integration lifecycle agent down

COMPOSE = docker compose --env-file .env -f deploy/compose.yaml
setup:
	python3 scripts/setup.py
install:
	uv sync --frozen --extra worker
check:
	uv run ruff check .
	uv run ruff format --check .
	uv run pytest -q tests/unit
	uv run python scripts/check_architecture.py
	uv run python scripts/export_specs.py --check
	uv run python scripts/check_content.py
specs:
	uv run python scripts/export_specs.py
package:
	uv build
	uv run python scripts/verify_package.py
build:
	docker build -f docker/worker.Dockerfile -t loop-sandbox-worker:local .
	$(COMPOSE) build
up:
	$(COMPOSE) up -d --wait
smoke:
	python3 tests/integration/smoke.py
mcp:
	uv run python tests/integration/mcp_sessions.py
rotation:
	uv run python tests/integration/token_rotation.py
# Enforce sequencing even with make -j.
integration:
	$(MAKE) smoke
	$(MAKE) mcp
	$(MAKE) rotation
	$(MAKE) lifecycle
lifecycle:
	python3 tests/integration/lifecycle.py
agent:
	python3 tests/integration/smoke.py --agent
down:
	$(COMPOSE) down
