# cgprr-neet-rag

A private, locally hosted RAG assistant for NEET (UG) counselling, built on public MCC documents,
plus a college predictor (Track A). No cloud LLM on the main path.

Status: scaffold only.

```bash
uv sync
cp .env.example .env        # set passwords
docker compose up -d postgres
make migrate && scripts/check_roles.sh
uv run pytest -q
uv run pre-commit install
```

## Running without Docker (macOS)

On a Mac you can skip Docker and use Homebrew's Postgres 18 with pgvector:

```bash
brew install postgresql@18 pgvector
brew services start postgresql@18
cp .env.example .env
# in .env: POSTGRES_HOST=localhost, POSTGRES_HOST_PORT=5432,
#          POSTGRES_USER=<your macOS user>  (the local superuser; used only for migrations)
make migrate                 # creates database "neet", schema, extensions and roles
scripts/check_roles.sh       # optional: prove neet_ingest / neet_reader permissions
```

`make migrate` runs `scripts/migrate.sh` with `psql` against whatever `.env` points at, so the same
command works for Homebrew Postgres and the compose container. Note that Homebrew's default
`pg_hba.conf` trusts local connections, so role passwords are not checked there; role privileges are.
