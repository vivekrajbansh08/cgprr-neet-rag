.PHONY: up migrate ingest index eval bench ui test lint

up:
	@echo "TODO: up (docker compose up -d postgres)"

migrate:
	@scripts/migrate.sh

ingest:
	@echo "TODO: ingest"

index:
	@echo "TODO: index"

eval:
	@echo "TODO: eval"

bench:
	@echo "TODO: bench"

ui:
	@echo "TODO: ui"

test:
	@echo "TODO: test (uv run pytest -q)"

lint:
	@echo "TODO: lint (uv run ruff check . && uv run ruff format --check .)"
