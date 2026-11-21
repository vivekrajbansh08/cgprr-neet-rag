"""The loaded database (schema neet) reproduces every oracle-derived value in eval/golden/questions.yaml.

Connects as neet_reader (read-only) and only reads; eval/golden is read, never written. Skips cleanly
when the database is unreachable or neet.allotment is empty (e.g. CI without the raw PDFs).
Every query is fixed, parameterised SQL. The predictor rule (scripts/oracle_predict.py) is computed in
SQL over neet.closing_rank, which already excludes CW/NRI rows.
"""

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg
import pytest
import yaml
from neet_common.config import Settings
from neet_common.db import connect
from neet_mccparse.text import squash

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = yaml.safe_load((ROOT / "eval" / "golden" / "questions.yaml").read_text(encoding="utf-8"))[
    "questions"
]
CLOSING = [
    (q["id"], i, v)
    for q in QUESTIONS
    for i, v in enumerate(q["expected_values"])
    if v.get("oracle", {}).get("kind") == "closing_rank"
]
PREDICTOR = [q for q in QUESTIONS if "inputs" in q and "expected_option_count" in q]
CHECKS = [(q["id"], c) for q in QUESTIONS for c in q.get("oracle_checks", [])]

CELL_SQL = """
SELECT i.name_norm, c.closing_rank, c.allotments, c.file, c.page, c.line
FROM neet.closing_rank c JOIN neet.institute i ON i.id = c.institute_id
WHERE c.round = %(round)s AND c.quota = %(quota)s AND c.course = %(course)s
  AND c.allotted_category = %(category)s AND strpos(i.name_norm, %(pattern)s) > 0
"""

# The pre-registered predictor rule, in SQL. Eligible allotted categories: {Open} for General, else
# {Open, C}; with PwD also each PwD variant. Scope: institutes with any eligible-category cell in the
# round (and, with a state filter, whose seat-matrix state matches). Option: closing rank >= AIR.
PREDICT_CTE = """
WITH base AS (
    SELECT unnest(CASE WHEN %(category)s = 'General' THEN ARRAY['Open']
                       ELSE ARRAY['Open', %(category)s::text] END) AS cat
), cats AS (
    SELECT cat FROM base UNION ALL SELECT cat || ' PwD' FROM base WHERE %(pwd)s
), scope AS (
    SELECT c.*, i.name_norm, i.state
    FROM neet.closing_rank c JOIN neet.institute i ON i.id = c.institute_id
    WHERE c.round = %(round)s AND c.quota = %(quota)s AND c.course = %(course)s
      AND c.allotted_category IN (SELECT cat FROM cats)
      AND (%(state)s::text IS NULL OR i.state = %(state)s::text)
)
"""
SCOPE_SQL = PREDICT_CTE + "SELECT count(DISTINCT institute_id) FROM scope"
OPTIONS_SQL = (
    PREDICT_CTE
    + """
SELECT name_norm, state, allotted_category, rank_text, allotments, page, line
FROM scope WHERE closing_rank >= %(rank)s ORDER BY name_norm, allotted_category
"""
)
MAX_SQL = (
    PREDICT_CTE
    + "SELECT closing_rank, allotments, file, page, line FROM scope"
    + " ORDER BY closing_rank DESC, page, line LIMIT 1"
)


@pytest.fixture(scope="module")
def db() -> Iterator[psycopg.Connection]:
    try:
        conn = connect(Settings(), "neet_reader", connect_timeout=3)
    except psycopg.OperationalError as exc:
        pytest.skip(f"database not reachable as neet_reader: {type(exc).__name__}")
    try:
        empty = conn.execute("SELECT count(*) FROM neet.allotment").fetchone()[0] == 0
    except psycopg.Error as exc:
        conn.close()
        pytest.skip(f"schema neet not ready: {type(exc).__name__}")
    if empty:
        conn.close()
        pytest.skip("neet.allotment is empty: run `make ingest`")
    yield conn
    conn.close()


def _params(i: dict[str, Any]) -> dict[str, Any]:
    return {
        "round": i["round"],
        "quota": i["quota"],
        "course": i["course"],
        "category": i["category"],
        "pwd": bool(i["pwd"]),
        "state": i["state"],
        "rank": Decimal(str(i["rank"])),
    }


@pytest.mark.parametrize(("qid", "idx", "v"), CLOSING, ids=[f"{q}[{i}]" for q, i, _ in CLOSING])
def test_closing_rank_value_matches_db(db: psycopg.Connection, qid: str, idx: int, v: dict[str, Any]) -> None:
    o = v["oracle"]
    rows = db.execute(
        CELL_SQL,
        {
            "round": o["round"],
            "quota": o["quota"],
            "course": o["course"],
            "category": o["category"],
            "pattern": squash(o["institute"]),
        },
    ).fetchall()
    assert len(rows) == 1, f"{qid}: {o['institute']!r} matches {len(rows)} institutes (must be exactly 1)"
    _, closing, allotments, file, page, line = rows[0]
    assert closing == Decimal(str(v["value"]))
    assert allotments == v["allotments"]
    assert (file, page, line) == (v["file"], v["page"], v["line"])


@pytest.mark.parametrize("q", PREDICTOR, ids=[q["id"] for q in PREDICTOR])
def test_predictor_rule_in_sql_matches_golden(db: psycopg.Connection, q: dict[str, Any]) -> None:
    p = _params(q["inputs"])
    assert db.execute(SCOPE_SQL, p).fetchone()[0] == q["institutes_in_scope"]
    options: dict[str, list[tuple[Any, ...]]] = {}
    for name_norm, state, cat, rank_text, n, page, line in db.execute(OPTIONS_SQL, p).fetchall():
        options.setdefault(name_norm, []).append((state, cat, rank_text, n, page, line))
    assert len(options) == q["expected_option_count"]
    for v in q["expected_values"]:
        if v.get("oracle", {}).get("kind") == "max_closing":
            closing, n, file, page, line = db.execute(MAX_SQL, p).fetchone()
            assert (closing, n, file, page, line) == (
                Decimal(str(v["value"])),
                v["allotments"],
                v["file"],
                v["page"],
                v["line"],
            )
            continue
        hits = [k for k in options if squash(v["institute_match"]) in k]
        assert len(hits) == 1, f"{q['id']}: {v['institute_match']!r} matches {len(hits)} options"
        cells = options[hits[0]]
        got = [
            {"category": c, "closing_rank": rt, "allotments": n, "page": pg, "line": ln}
            for _, c, rt, n, pg, ln in cells
        ]
        assert sorted(got, key=lambda c: c["category"]) == sorted(v["cells"], key=lambda c: c["category"])
        assert {s for s, *_ in cells} == {v["state"]}


@pytest.mark.parametrize(("qid", "check"), CHECKS, ids=[f"{q}:{c['kind']}" for q, c in CHECKS])
def test_refusal_preconditions_hold_in_db(db: psycopg.Connection, qid: str, check: dict[str, Any]) -> None:
    if check["kind"] == "no_cell":
        rows = db.execute(
            CELL_SQL,
            {
                "round": check["round"],
                "quota": check["quota"],
                "course": check["course"],
                "category": check["category"],
                "pattern": squash(check["institute"]),
            },
        ).fetchall()
        assert rows == []
    elif check["kind"] == "institute_absent":
        n = db.execute(
            "SELECT count(*) FROM neet.institute i WHERE strpos(i.name_norm, %s) > 0"
            " AND EXISTS (SELECT 1 FROM neet.allotment a WHERE a.institute_id = i.id AND a.round = ANY(%s))",
            (squash(check["pattern"]), check["rounds"]),
        ).fetchone()[0]
        assert n == 0
    else:
        pytest.fail(f"{qid}: unknown oracle check {check['kind']}")
