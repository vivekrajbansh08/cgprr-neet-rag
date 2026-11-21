-- 003: core tables for NEET-UG 2025 MCC data, the closing-rank views and the retrieval chunks.
-- Run as the database owner. Idempotent: IF NOT EXISTS / CREATE OR REPLACE throughout.
-- Row-level allotment data lives only in this local database; it is never exported or committed.

CREATE TABLE IF NOT EXISTS neet.source_file (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    file_name    text NOT NULL UNIQUE,
    sha256       text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    url          text NOT NULL,
    pages        integer,
    retrieved_at text
);

CREATE TABLE IF NOT EXISTS neet.institute (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name_norm        text NOT NULL UNIQUE,  -- squash(): lower-case, all whitespace removed
    display_name     text NOT NULL,
    raw_name         text NOT NULL,
    state            text,                  -- seat-matrix StateName only, never address text
    state_source     text,                  -- 'seat_matrix:<file>' or NULL
    seat_matrix_code text
);

CREATE TABLE IF NOT EXISTS neet.allotment (
    id                 bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_file_id     bigint NOT NULL REFERENCES neet.source_file (id),
    round              smallint NOT NULL CHECK (round BETWEEN 1 AND 3),
    page               integer NOT NULL,
    line               integer NOT NULL,
    sno                integer,
    rank               numeric NOT NULL,
    rank_text          text NOT NULL,
    quota              text NOT NULL,
    institute_id       bigint NOT NULL REFERENCES neet.institute (id),
    course             text NOT NULL,
    allotted_category  text NOT NULL,
    candidate_category text NOT NULL,       -- verbatim ("GNYes" kept as printed)
    remark             text NOT NULL,
    is_cw_nri          boolean NOT NULL,
    UNIQUE (source_file_id, page, line)
);
CREATE INDEX IF NOT EXISTS allotment_cell_idx
    ON neet.allotment (round, quota, course, allotted_category, institute_id);

CREATE TABLE IF NOT EXISTS neet.seat_matrix (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    institute_id     bigint REFERENCES neet.institute (id),
    seat_matrix_code text NOT NULL,
    quota            text NOT NULL,
    course           text NOT NULL,
    category         text NOT NULL,
    seats            integer NOT NULL CHECK (seats >= 0),
    file             text NOT NULL,
    page             integer NOT NULL,
    line             integer NOT NULL
);

CREATE OR REPLACE VIEW neet.closing_rank AS
SELECT DISTINCT ON (a.round, a.quota, a.institute_id, a.course, a.allotted_category)
       a.round, a.quota, a.institute_id, a.course, a.allotted_category,
       a.rank AS closing_rank,
       count(*) OVER w AS allotments,
       f.file_name AS file, a.page, a.line, a.rank_text
FROM neet.allotment a
JOIN neet.source_file f ON f.id = a.source_file_id
WHERE NOT a.is_cw_nri
WINDOW w AS (PARTITION BY a.round, a.quota, a.institute_id, a.course, a.allotted_category)
ORDER BY a.round, a.quota, a.institute_id, a.course, a.allotted_category,
         a.rank DESC, a.page DESC, a.line DESC;

CREATE OR REPLACE VIEW neet.closing_rank_cw_nri AS
SELECT DISTINCT ON (a.round, a.quota, a.institute_id, a.course, a.allotted_category)
       a.round, a.quota, a.institute_id, a.course, a.allotted_category,
       a.rank AS closing_rank,
       count(*) OVER w AS allotments,
       f.file_name AS file, a.page, a.line, a.rank_text
FROM neet.allotment a
JOIN neet.source_file f ON f.id = a.source_file_id
WHERE a.is_cw_nri
WINDOW w AS (PARTITION BY a.round, a.quota, a.institute_id, a.course, a.allotted_category)
ORDER BY a.round, a.quota, a.institute_id, a.course, a.allotted_category,
         a.rank DESC, a.page DESC, a.line DESC;

CREATE TABLE IF NOT EXISTS neet.chunk (
    id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    kind              text NOT NULL CHECK (kind IN ('cell', 'note')),
    text              text NOT NULL,
    embedding         vector(1024),
    tsv               tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,
    round             smallint,
    quota             text,
    institute_id      bigint REFERENCES neet.institute (id),
    course            text,
    allotted_category text,
    is_cw_nri         boolean,
    note              text,                 -- note pointer, e.g. 'quota_legend', 'r2_revision_notice'
    file              text NOT NULL,
    page              integer NOT NULL,
    line              integer
);
CREATE INDEX IF NOT EXISTS chunk_embedding_hnsw ON neet.chunk USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS chunk_tsv_gin ON neet.chunk USING gin (tsv);

CREATE TABLE IF NOT EXISTS neet.ingest_run (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    started_at   timestamptz NOT NULL,
    finished_at  timestamptz,
    git_commit   text,
    input_sha256 jsonb NOT NULL,
    counts       jsonb NOT NULL
);

-- Grants. Default privileges (002) already cover owner-created tables; restated explicitly so this
-- file is correct on its own, and views need the SELECT grant too.
GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE
    ON neet.source_file, neet.institute, neet.allotment, neet.seat_matrix, neet.chunk, neet.ingest_run
    TO neet_ingest;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA neet TO neet_ingest;
GRANT SELECT
    ON neet.source_file, neet.institute, neet.allotment, neet.seat_matrix, neet.chunk, neet.ingest_run,
       neet.closing_rank, neet.closing_rank_cw_nri
    TO neet_reader;
GRANT SELECT ON neet.closing_rank, neet.closing_rank_cw_nri TO neet_ingest;
