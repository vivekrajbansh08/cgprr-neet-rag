#!/usr/bin/env bash
# Apply db/migrations/*.sql in order, against whatever .env points at (local brew Postgres or the
# compose container). Creates POSTGRES_DB if missing. Each file runs once; applied files are
# recorded in neet.schema_migrations with their sha256. Every migration is itself idempotent too.
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -f .env ]] || { echo "ERROR: .env not found (cp .env.example .env)" >&2; exit 1; }
set -a; source .env; set +a

export PGHOST="${POSTGRES_HOST:-localhost}" PGPORT="${POSTGRES_HOST_PORT:-5432}" PGUSER="$POSTGRES_USER"
if [[ -n "${POSTGRES_PASSWORD:-}" ]]; then export PGPASSWORD="$POSTGRES_PASSWORD"; fi
DB="${POSTGRES_DB:-neet}"
PSQL=(psql -X -q -v ON_ERROR_STOP=1)

echo "target: $PGUSER@$PGHOST:$PGPORT/$DB"
if [[ -z $("${PSQL[@]}" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$DB'") ]]; then
  "${PSQL[@]}" -d postgres -c "CREATE DATABASE \"$DB\""
  echo "create database $DB"
fi
export PGDATABASE="$DB"

"${PSQL[@]}" -c "CREATE SCHEMA IF NOT EXISTS neet;
  CREATE TABLE IF NOT EXISTS neet.schema_migrations (
    filename text PRIMARY KEY, sha256 text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now());"

for f in db/migrations/*.sql; do
  name=$(basename "$f")
  sum=$(shasum -a 256 "$f" | cut -d' ' -f1)
  applied=$("${PSQL[@]}" -tAc "SELECT sha256 FROM neet.schema_migrations WHERE filename = '$name'")
  if [[ -n "$applied" ]]; then
    [[ "$applied" == "$sum" ]] || { echo "ERROR: $name changed after it was applied" >&2; exit 1; }
    echo "skip   $name (already applied)"
    continue
  fi
  "${PSQL[@]}" --single-transaction -f "$f"
  "${PSQL[@]}" -c "INSERT INTO neet.schema_migrations (filename, sha256) VALUES ('$name', '$sum')"
  echo "apply  $name"
done
