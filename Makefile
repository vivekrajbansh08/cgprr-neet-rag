.PHONY: up migrate ingest index report eval bench ui test lint

up:
	@echo "TODO: up (docker compose up -d postgres)"

migrate:
	@scripts/migrate.sh

ingest:
	uv run python -m neet_ingest

index:
	uv run python -m neet_ingest.index

report:
	uv run python -m neet_ingest.report

eval:
	@echo "TODO: eval"

bench:
	@echo "TODO: bench"

ui:
	@echo "TODO: ui"

test:
	uv run pytest -q

lint:
	uv run ruff check . && uv run ruff format --check .
