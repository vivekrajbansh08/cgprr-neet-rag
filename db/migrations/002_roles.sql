-- 002: application roles. Run as a superuser / database owner. Idempotent: safe to re-run.
--   neet_ingest: write on schema neet: create/drop its own tables, and read/write all neet tables.
--   neet_reader: SELECT only, read-only transactions. Used by the services and the MCP server.
-- Passwords are read from the environment by psql (\getenv, psql >= 15) so they never appear in argv.
\getenv ingest_password NEET_INGEST_PASSWORD
\getenv reader_password NEET_READER_PASSWORD

SELECT 'CREATE ROLE neet_ingest LOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'neet_ingest') \gexec
SELECT 'CREATE ROLE neet_reader LOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'neet_reader') \gexec

ALTER ROLE neet_ingest WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT PASSWORD :'ingest_password';
ALTER ROLE neet_reader WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT PASSWORD :'reader_password';

ALTER ROLE neet_ingest SET search_path = neet, public;
ALTER ROLE neet_reader SET search_path = neet, public;
ALTER ROLE neet_reader SET default_transaction_read_only = on;
ALTER ROLE neet_reader SET statement_timeout = '10s';

-- Database access: only these roles (and superusers / the owner) may connect.
SELECT format('REVOKE ALL ON DATABASE %I FROM PUBLIC', current_database()) \gexec
SELECT format('GRANT CONNECT ON DATABASE %I TO neet_ingest, neet_reader', current_database()) \gexec

-- Schema neet
GRANT USAGE, CREATE ON SCHEMA neet TO neet_ingest;
GRANT USAGE ON SCHEMA neet TO neet_reader;
REVOKE CREATE ON SCHEMA neet FROM neet_reader;

-- Existing objects
GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA neet TO neet_ingest;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA neet TO neet_ingest;
GRANT SELECT ON ALL TABLES IN SCHEMA neet TO neet_reader;

-- Future objects created by the migration user (this session's role)
ALTER DEFAULT PRIVILEGES IN SCHEMA neet
    GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON TABLES TO neet_ingest;
ALTER DEFAULT PRIVILEGES IN SCHEMA neet
    GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO neet_ingest;
ALTER DEFAULT PRIVILEGES IN SCHEMA neet
    GRANT SELECT ON TABLES TO neet_reader;

-- Future objects created by neet_ingest are readable by neet_reader
ALTER DEFAULT PRIVILEGES FOR ROLE neet_ingest IN SCHEMA neet
    GRANT SELECT ON TABLES TO neet_reader;
