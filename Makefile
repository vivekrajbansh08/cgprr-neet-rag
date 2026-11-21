.PHONY: web web-build web-check up migrate ingest index report serve stop eval bench ui test lint

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

serve:
	@scripts/serve.sh start

stop:
	@scripts/serve.sh stop

eval:
	uv run python -m neet_eval

bench:
	uv run python -m neet_bench

ui:
	@echo "TODO: ui"

test:
	uv run pytest -q

lint:
	uv run ruff check . && uv run ruff format --check .

web:
	cd services/web && npm run dev

web-build:
	cd services/web && npm ci && npm run build

web-check:
	cd services/web && npm run contrast && npx playwright test
