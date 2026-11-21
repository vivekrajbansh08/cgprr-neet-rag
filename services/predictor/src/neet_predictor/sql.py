"""Fixed, parameterised SQL for the predictor. Nothing here is built from request input.

Reads neet.closing_rank (CW / NRI allotments already excluded), never neet.closing_rank_cw_nri.
The state filter is applied in Python (neet_predictor.rule) so unplaced institutes can be counted.
"""

from __future__ import annotations

from decimal import Decimal

import psycopg
from psycopg_pool import ConnectionPool

from neet_predictor.rule import Row

ROWS = """
SELECT c.institute_id, i.display_name, i.state, c.round, c.quota, c.course, c.allotted_category,
       c.closing_rank, c.rank_text, c.allotments, c.file, c.page, c.line, f.sha256
FROM neet.closing_rank c
JOIN neet.institute i ON i.id = c.institute_id
JOIN neet.source_file f ON f.file_name = c.file
WHERE c.round = %(round)s AND c.quota = %(quota)s AND c.course = %(course)s
  AND c.allotted_category = ANY(%(cats)s::text[])
ORDER BY c.institute_id, c.allotted_category
"""

QUOTAS = "SELECT DISTINCT quota FROM neet.closing_rank ORDER BY quota"
COURSES = "SELECT DISTINCT course FROM neet.closing_rank ORDER BY course"
STATES = "SELECT DISTINCT state FROM neet.institute WHERE state IS NOT NULL ORDER BY state"


def fetch_rows(pool: ConnectionPool, *, round_: int, quota: str, course: str, cats: list[str]) -> list[Row]:
    with pool.connection() as conn:
        cur = conn.execute(ROWS, {"round": round_, "quota": quota, "course": course, "cats": cats})
        return [
            Row(
                institute_id=iid,
                institute=name,
                state=state,
                round=rnd,
                quota=q,
                course=c,
                category=cat,
                closing_rank=Decimal(closing),
                rank_text=rank_text,
                allotments=int(n),
                file=file,
                page=page,
                line=line,
                source_sha256=sha,
            )
            for iid, name, state, rnd, q, c, cat, closing, rank_text, n, file, page, line, sha in cur
        ]


def _column(conn: psycopg.Connection, sql: str) -> list[str]:
    return [r[0] for r in conn.execute(sql)]


def form_values(pool: ConnectionPool) -> tuple[list[str], list[str], list[str]]:
    """(quotas, courses, states) for the web form dropdowns."""
    with pool.connection() as conn:
        return _column(conn, QUOTAS), _column(conn, COURSES), _column(conn, STATES)
