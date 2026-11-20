-- 001: extensions and the application schema. Run as the database owner (POSTGRES_USER).
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE SCHEMA IF NOT EXISTS neet;
COMMENT ON SCHEMA neet IS 'NEET counselling RAG: documents, chunks, closing ranks. Public data only.';

-- Nobody but the owner creates objects in public.
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
