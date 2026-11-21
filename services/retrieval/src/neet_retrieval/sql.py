"""Fixed, parameterised SQL for the retrieval service. Nothing here is built from request input."""

INSTITUTES = "SELECT id, display_name, state FROM neet.institute ORDER BY id"

# Signal 1: trigram similarity of the query against the institute display string.
TRGM_INSTITUTES = """
SELECT id
FROM neet.institute
ORDER BY greatest(word_similarity(%(q)s, lower(display_name)), similarity(%(q)s, lower(display_name))) DESC,
         id
LIMIT %(k)s
"""

# Signal 2: full-text search over cell chunks, mapped to the institute. %(q)s is a websearch query.
FTS_INSTITUTES = """
SELECT institute_id
FROM (
    SELECT c.institute_id, max(ts_rank(c.tsv, q)) AS r
    FROM neet.chunk c, websearch_to_tsquery('english', %(q)s) q
    WHERE c.kind = 'cell' AND c.institute_id IS NOT NULL AND c.tsv @@ q
    GROUP BY c.institute_id
) s
ORDER BY r DESC, institute_id
LIMIT %(k)s
"""

# HNSW returns at most ef_search rows; widen it for the per-institute grouping below.
SET_EF_SEARCH = "SET LOCAL hnsw.ef_search = 200"

# Signal 3: vector search over cell chunks, mapped to the institute (best chunk per institute).
VEC_INSTITUTES = """
SELECT institute_id
FROM (
    SELECT institute_id, embedding <=> %(v)s::vector AS d
    FROM neet.chunk
    WHERE kind = 'cell' AND embedding IS NOT NULL
    ORDER BY embedding <=> %(v)s::vector
    LIMIT 200
) s
GROUP BY institute_id
ORDER BY min(d), institute_id
LIMIT %(k)s
"""

# Exact closing-rank rows for one institute, optionally narrowed; CW/NRI rows flagged is_cw_nri.
CELLS = """
SELECT * FROM (
    SELECT c.round, c.quota, c.institute_id, c.course, c.allotted_category, c.closing_rank, c.rank_text,
           c.allotments, c.file, c.page, c.line, i.display_name, i.state, false AS is_cw_nri, f.sha256
    FROM neet.closing_rank c JOIN neet.institute i ON i.id = c.institute_id
    JOIN neet.source_file f ON f.file_name = c.file
    WHERE c.institute_id = %(iid)s
      AND (%(round)s::int IS NULL OR c.round = %(round)s::int)
      AND (%(quota)s::text IS NULL OR c.quota = %(quota)s::text)
      AND (%(course)s::text IS NULL OR c.course = %(course)s::text)
      AND (%(cat)s::text IS NULL OR c.allotted_category = %(cat)s::text)
    UNION ALL
    SELECT c.round, c.quota, c.institute_id, c.course, c.allotted_category, c.closing_rank, c.rank_text,
           c.allotments, c.file, c.page, c.line, i.display_name, i.state, true AS is_cw_nri, f.sha256
    FROM neet.closing_rank_cw_nri c JOIN neet.institute i ON i.id = c.institute_id
    JOIN neet.source_file f ON f.file_name = c.file
    WHERE c.institute_id = %(iid)s
      AND (%(round)s::int IS NULL OR c.round = %(round)s::int)
      AND (%(quota)s::text IS NULL OR c.quota = %(quota)s::text)
      AND (%(course)s::text IS NULL OR c.course = %(course)s::text)
      AND (%(cat)s::text IS NULL OR c.allotted_category = %(cat)s::text)
      AND %(cw)s
) u
ORDER BY round, quota, course, allotted_category, is_cw_nri
LIMIT %(lim)s
"""

FTS_CHUNKS = """
SELECT c.id
FROM neet.chunk c, websearch_to_tsquery('english', %(q)s) q
WHERE c.tsv @@ q AND (%(kind)s::text IS NULL OR c.kind = %(kind)s::text)
ORDER BY ts_rank(c.tsv, q) DESC, c.id
LIMIT %(k)s
"""

VEC_CHUNKS = """
SELECT id
FROM neet.chunk
WHERE embedding IS NOT NULL AND (%(kind)s::text IS NULL OR kind = %(kind)s::text)
ORDER BY embedding <=> %(v)s::vector, id
LIMIT %(k)s
"""

CHUNKS_BY_ID = """
SELECT id, kind, note, text, file, page, line FROM neet.chunk WHERE id = ANY(%(ids)s)
"""
