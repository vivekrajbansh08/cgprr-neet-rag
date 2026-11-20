#!/usr/bin/env bash
# Prove neet_ingest / neet_reader permissions with raw psql output (psql -e echoes each statement).
# Expected: ingest creates, inserts into and drops a table in neet; reader can SELECT but
# INSERT, CREATE and DROP are refused. Exits non-zero if any expectation fails.
set -uo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a
export PGHOST="${POSTGRES_HOST:-localhost}" PGPORT="${POSTGRES_HOST_PORT:-5432}" PGDATABASE="${POSTGRES_DB:-neet}"
fail=0

run() { # run <role> <password> <expect ok|error> <sql>
  local role=$1 pw=$2 want=$3 sql=$4 rc
  echo "--- psql as $role (expect: $want)"
  PGUSER=$role PGPASSWORD=$pw psql -X -e -v ON_ERROR_STOP=1 -c "$sql" 2>&1
  rc=$?
  if [[ $want == ok && $rc -ne 0 ]] || [[ $want == error && $rc -eq 0 ]]; then
    echo "!!! UNEXPECTED (exit $rc)"; fail=1
  fi
}
ingest() { run neet_ingest "$NEET_INGEST_PASSWORD" "$@"; }
reader() { run neet_reader "$NEET_READER_PASSWORD" "$@"; }

ingest ok    "SELECT current_user, current_setting('search_path') AS search_path"
ingest ok    "CREATE TABLE neet.role_check (id int PRIMARY KEY, note text)"
ingest ok    "INSERT INTO neet.role_check VALUES (1, 'written by neet_ingest')"

reader ok    "SELECT current_user, current_setting('default_transaction_read_only') AS read_only"
reader ok    "SELECT * FROM neet.role_check"
reader error "INSERT INTO neet.role_check VALUES (2, 'should fail')"
reader error "CREATE TABLE neet.reader_table (id int)"
reader error "DROP TABLE neet.role_check"

# Defence in depth: even with read-only transactions switched off, privileges still refuse.
echo "=== neet_reader with default_transaction_read_only=off (privilege layer only)"
export PGOPTIONS="-c default_transaction_read_only=off"
reader error "INSERT INTO neet.role_check VALUES (2, 'should fail')"
reader error "CREATE TABLE neet.reader_table (id int)"
reader error "DROP TABLE neet.role_check"
unset PGOPTIONS

ingest ok    "DROP TABLE neet.role_check"

echo
((fail == 0)) && echo "RESULT: all role checks behaved as intended" || { echo "RESULT: FAILED"; exit 1; }
