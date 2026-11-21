"""CLI: evidence that the database matches the raw PDFs. Connects as neet_reader (read-only).

Prints the report and writes logs/ingest_report.md (logs/ is gitignored).
Usage: uv run python -m neet_ingest.report
"""

from __future__ import annotations

import re
from pathlib import Path

import psycopg
from neet_common.config import REPO_ROOT, Settings
from neet_common.db import connect
from neet_mccparse.text import pdftotext_pages
from psycopg import sql

from neet_ingest.manifest import sha256_of

RAW_DIR = REPO_ROOT / "data" / "raw" / "mcc" / "2025"
REPORT = REPO_ROOT / "logs" / "ingest_report.md"
EXPECTED_ROWS = {"1": 26608, "2": 35551, "3": 39479}
EXPECTED_ALLOTMENTS = {1: 26608, 2: 15321, 3: 9143}
EXPECTED_KEYWORDS = {2: (12901, 2420), 3: (5529, 3614)}
FRESH = re.compile(r"Fresh Allotted")
UPGRADED = re.compile(r"Upgraded(?:\s*$|\()")
SEED = 20251121
SAMPLE = 25
TABLES = ("source_file", "institute", "allotment", "seat_matrix", "chunk", "ingest_run")
VIEWS = ("closing_rank", "closing_rank_cw_nri")
# Seat-matrix cells allowed to have more R1 allotments than seats, each with a written reason:
# (institute display_name, quota, course, category). Empty: no such cell is explained yet.
GT_ALLOWED: frozenset[tuple[str, str, str, str]] = frozenset()

Section = tuple[list[str], bool]  # report lines, passed?


def raw_path_checked(conn: psycopg.Connection, file: str) -> Path | None:
    """data/raw path of a source file, or None if its sha256 differs from neet.source_file."""
    row = conn.execute("SELECT sha256 FROM neet.source_file WHERE file_name = %s", (file,)).fetchone()
    path = next(RAW_DIR.rglob(file), None)
    if row is None or path is None or sha256_of(path) != row[0]:
        return None
    return path


def ok(flag: bool) -> str:
    return "OK" if flag else "MISMATCH"


def section_counts(conn: psycopg.Connection) -> Section:
    out = ["## 1. Row counts and keyword reconciliation", ""]
    run_id, counts = conn.execute(
        "SELECT id, counts FROM neet.ingest_run ORDER BY id DESC LIMIT 1"
    ).fetchone()
    rows = counts["rows_per_round"]
    passed = rows == EXPECTED_ROWS
    out.append(
        f"ingest_run {run_id}: rows per round {rows} expected {EXPECTED_ROWS}: {ok(rows == EXPECTED_ROWS)}"
    )
    db = dict(
        conn.execute("SELECT round, count(*) FROM neet.allotment GROUP BY round ORDER BY round").fetchall()
    )
    passed = passed and db == EXPECTED_ALLOTMENTS
    out.append(
        f"allotments per round in DB {db} expected {EXPECTED_ALLOTMENTS}: {ok(db == EXPECTED_ALLOTMENTS)}"
    )
    for rnd, (exp_fresh, exp_up) in EXPECTED_KEYWORDS.items():
        path = raw_path_checked(conn, f"r{rnd}_allotment_final.pdf")
        if path is None:
            out.append(f"R{rnd}: FAIL raw PDF missing or sha256 differs from neet.source_file")
            passed = False
            continue
        text = "\n".join(pdftotext_pages(path)).split("\n")
        pdf_fresh = sum(bool(FRESH.search(ln)) for ln in text)
        pdf_up = sum(bool(UPGRADED.search(ln)) for ln in text)
        db_fresh, db_up = conn.execute(
            "SELECT count(*) FILTER (WHERE remark LIKE 'Fresh Allotted%%'),"
            " count(*) FILTER (WHERE remark LIKE 'Upgraded%%') FROM neet.allotment WHERE round = %s",
            (rnd,),
        ).fetchone()
        good = pdf_fresh == db_fresh == exp_fresh and pdf_up == db_up == exp_up
        passed = passed and good
        out.append(
            f"R{rnd}: 'Fresh Allotted' lines in PDF {pdf_fresh} / DB {db_fresh} (expected {exp_fresh});"
            f" 'Upgraded' lines in PDF {pdf_up} / DB {db_up} (expected {exp_up}): {ok(good)}"
        )
    return out, passed


SEAT_SQL = """
WITH a AS (
    SELECT institute_id, quota, course, allotted_category AS category, count(*) AS n
    FROM neet.allotment WHERE round = 1 GROUP BY 1, 2, 3, 4
), s AS (
    -- A cell printed in two seat matrices (BHU is in both AIIMS/BHU/JIPMER and central universities)
    -- is one cell: take its seats once; section 2 reports how many such cells disagree.
    SELECT institute_id, quota, course, category, max(seats) AS seats
    FROM neet.seat_matrix WHERE institute_id IS NOT NULL GROUP BY 1, 2, 3, 4
)
SELECT i.display_name, s.quota, s.course, s.category, s.seats, coalesce(a.n, 0) AS n
FROM s JOIN neet.institute i ON i.id = s.institute_id
LEFT JOIN a USING (institute_id, quota, course, category)
ORDER BY i.name_norm, s.quota, s.course, s.category
"""
NO_SEAT_SQL = """
SELECT count(*) FROM (
    SELECT DISTINCT institute_id, quota, course, allotted_category FROM neet.allotment a
    WHERE round = 1 AND NOT EXISTS (
        SELECT 1 FROM neet.seat_matrix s WHERE s.institute_id = a.institute_id AND s.quota = a.quota
          AND s.course = a.course AND s.category = a.allotted_category)
) x
"""
NO_SEAT_BREAKDOWN_SQL = """
SELECT a.course, a.quota, count(DISTINCT (a.institute_id, a.allotted_category)),
       count(DISTINCT a.institute_id)
FROM neet.allotment a
WHERE round = 1 AND NOT EXISTS (
    SELECT 1 FROM neet.seat_matrix s WHERE s.institute_id = a.institute_id AND s.quota = a.quota
      AND s.course = a.course AND s.category = a.allotted_category)
GROUP BY 1, 2 ORDER BY 3 DESC, 1, 2
"""


def section_seats(conn: psycopg.Connection) -> Section:
    out = ["## 2. Round 1 seat-matrix reconciliation (CW/NRI rows included)", ""]
    rows = conn.execute(SEAT_SQL).fetchall()
    eq = sum(r[5] == r[4] for r in rows)
    lt = [r for r in rows if r[5] < r[4]]
    gt = [r for r in rows if r[5] > r[4]]
    dup = conn.execute(
        "SELECT count(*), count(*) FILTER (WHERE min_s <> max_s) FROM ("
        " SELECT min(seats) AS min_s, max(seats) AS max_s FROM neet.seat_matrix"
        " WHERE institute_id IS NOT NULL GROUP BY institute_id, quota, course, category"
        " HAVING count(*) > 1) d"
    ).fetchone()
    out.append(f"seat-matrix cells compared (linked to an institute): {len(rows)}")
    out.append(f"  cells printed in two seat matrices: {dup[0]} (with differing seat counts: {dup[1]})")
    out.append(f"allotments == seats: {eq}; allotments < seats: {len(lt)}; allotments > seats: {len(gt)}")
    out.append(f"  of the < cells, with zero R1 allotments: {sum(r[5] == 0 for r in lt)}")
    unexplained = 0
    for name, quota, course, cat, seats, n in gt:
        allowed = (name, quota, course, cat) in GT_ALLOWED
        unexplained += not allowed
        tag = "allow-listed" if allowed else "FAIL (not on GT_ALLOWED)"
        out.append(f"  > {name[:70]} | {quota} | {course} | {cat} | seats {seats} | allotments {n} | {tag}")
    unlinked = conn.execute(
        "SELECT count(*), count(DISTINCT seat_matrix_code), coalesce(sum(seats), 0)"
        " FROM neet.seat_matrix WHERE institute_id IS NULL"
    ).fetchone()
    out.append(
        f"seat-matrix cells not matched to an institute: {unlinked[0]}"
        f" ({unlinked[1]} institute codes, {unlinked[2]} seats)"
    )
    out.append(f"R1 allotment cells with no seat-matrix entry: {conn.execute(NO_SEAT_SQL).fetchone()[0]}")
    for course, quota, n, insts in conn.execute(NO_SEAT_BREAKDOWN_SQL).fetchall():
        out.append(f"  {course} | {quota}: {n} cells, {insts} institutes")
    return out, unexplained == 0


def section_provenance(conn: psycopg.Connection) -> Section:
    out = ["## 3. Provenance re-extraction", ""]
    total = conn.execute("SELECT count(*) FROM neet.closing_rank").fetchone()[0]
    # Deterministic pseudo-random sample: order by md5(seed || cell pointer).
    sample = conn.execute(
        "SELECT c.round, c.file, c.page, c.line, c.rank_text, a.sno FROM neet.closing_rank c"
        " JOIN neet.source_file f ON f.file_name = c.file"
        " JOIN neet.allotment a ON a.source_file_id = f.id AND a.page = c.page AND a.line = c.line"
        " ORDER BY md5(%s || ':' || c.file || ':' || c.page || ':' || c.line) LIMIT %s",
        (str(SEED), SAMPLE),
    ).fetchall()
    out.append(f"seed {SEED} (md5 order): {len(sample)} of {total} closing_rank cells")
    fails = []
    checked: dict[str, Path | None] = {}
    for rnd, file, page, line, rank_text, sno in sample:
        if file not in checked:
            checked[file] = raw_path_checked(conn, file)
        path = checked[file]
        if path is None:
            fails.append(f"  FAIL R{rnd} {file}: raw PDF missing or sha256 differs from neet.source_file")
            continue
        lines = pdftotext_pages(path, page, page)[0].split("\n")
        got = lines[line - 1] if 0 < line <= len(lines) else ""
        lead = rf"{sno}\s+" if sno is not None else ""
        if not re.match(rf"^ {{0,2}}{lead}{re.escape(rank_text)}(?=\s)", got):
            fails.append(f"  FAIL R{rnd} {file} p{page} l{line} rank {rank_text}: {got[:40]!r}")
    out.append(f"rank_text found at the stored line: {len(sample) - len(fails)}/{len(sample)}")
    out.append(
        f"raw files sha256-checked against neet.source_file: {sum(p is not None for p in checked.values())}"
        f"/{len(checked)}"
    )
    return out + fails, not fails and len(sample) == SAMPLE


def section_size(conn: psycopg.Connection) -> Section:
    out = ["## 4. Database size and row counts", ""]
    size = conn.execute("SELECT pg_size_pretty(pg_database_size(current_database()))").fetchone()[0]
    out.append(f"database size: {size}")
    for t in (*TABLES, *VIEWS):
        n = conn.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier("neet", t))).fetchone()[0]
        out.append(f"neet.{t}: {n}")
    kinds = conn.execute(
        "SELECT kind, count(*), count(embedding) FROM neet.chunk GROUP BY kind ORDER BY kind"
    )
    for kind, n, emb in kinds.fetchall():
        out.append(f"  chunk kind {kind}: {n} ({emb} with embeddings)")
    return out, True  # informational


def main() -> int:
    with connect(Settings(), "neet_reader") as conn:
        lines = ["# Ingest report", ""]
        failed: list[str] = []
        for section in (section_counts, section_seats, section_provenance, section_size):
            body, passed = section(conn)
            lines += [*body, ""]
            if not passed:
                failed.append(body[0].lstrip("# "))
    lines.append("REPORT: PASS" if not failed else "REPORT: FAIL (" + "; ".join(failed) + ")")
    text = "\n".join(lines)
    print(text)
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text(text, encoding="utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
