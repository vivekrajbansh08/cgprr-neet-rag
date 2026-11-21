"""Load parsed rows into Postgres in one transaction, replacing the previous data (idempotent)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import psycopg
from neet_mccparse.text import squash

from neet_ingest.build import ALLOTMENT_FILES, Parsed, is_cw_nri
from neet_ingest.manifest import ManifestEntry

# No RESTART IDENTITY: that needs sequence ownership, which neet_ingest does not have.
TRUNCATE = "TRUNCATE neet.chunk, neet.allotment, neet.seat_matrix, neet.institute, neet.source_file"


def counts_of(parsed: Parsed, seat_rows: int, seat_linked: int) -> dict[str, object]:
    return {
        "rows_per_round": {str(r): n for r, n in sorted(parsed.rows_per_round.items())},
        "allotments_per_round": {str(r): len(v) for r, v in sorted(parsed.allotments.items())},
        "cw_nri_per_round": {
            str(r): sum(is_cw_nri(a) for a in v) for r, v in sorted(parsed.allotments.items())
        },
        "institutes": len(parsed.institutes),
        "institutes_with_state": sum(i.state is not None for i in parsed.institutes),
        "seat_matrix_rows": seat_rows,
        "seat_matrix_rows_linked": seat_linked,
    }


def load(
    conn: psycopg.Connection,
    parsed: Parsed,
    manifest: dict[str, ManifestEntry],
    git_commit: str | None,
    started_at: datetime,
) -> dict[str, object]:
    """Replace all ingested data in one transaction and record an ingest_run. Returns its counts."""
    with conn.transaction(), conn.cursor() as cur:
        cur.execute(TRUNCATE)
        file_ids: dict[str, int] = {}
        for name, e in sorted(manifest.items()):
            cur.execute(
                "INSERT INTO neet.source_file (file_name, sha256, url, pages, retrieved_at)"
                " VALUES (%s, %s, %s, %s, %s) RETURNING id",
                (name, e.sha256, e.url, e.pages, e.retrieved_at),
            )
            file_ids[name] = cur.fetchone()[0]
        inst_ids: dict[str, int] = {}
        for i in parsed.institutes:
            cur.execute(
                "INSERT INTO neet.institute (name_norm, display_name, raw_name, state, state_source,"
                " seat_matrix_code) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
                (i.name_norm, i.display_name, i.raw_name, i.state, i.state_source, i.seat_matrix_code),
            )
            inst_ids[i.name_norm] = cur.fetchone()[0]
        with cur.copy(
            "COPY neet.allotment (source_file_id, round, page, line, sno, rank, rank_text, quota,"
            " institute_id, course, allotted_category, candidate_category, remark, is_cw_nri) FROM STDIN"
        ) as cp:
            for rnd, rows in sorted(parsed.allotments.items()):
                fid = file_ids[ALLOTMENT_FILES[rnd]]
                for a in rows:
                    cp.write_row(
                        (
                            fid, rnd, a.page, a.line, a.sno, a.rank, a.rank_text, a.quota,
                            inst_ids[squash(a.institute)], a.course, a.allotted_category,
                            a.candidate_category, a.remarks, is_cw_nri(a),
                        )
                    )  # fmt: skip
        by_code: dict[str, list[int]] = {}
        for i in parsed.institutes:
            if i.seat_matrix_code:
                by_code.setdefault(i.seat_matrix_code, []).append(inst_ids[i.name_norm])
        linked = 0
        with cur.copy(
            "COPY neet.seat_matrix (institute_id, seat_matrix_code, quota, course, category, seats,"
            " file, page, line) FROM STDIN"
        ) as cp:
            for c in parsed.seat_cells:
                ids = by_code.get(c.code, [])
                iid = ids[0] if len(ids) == 1 else None  # a code shared by two institutes: no link
                linked += iid is not None
                cp.write_row((iid, c.code, c.quota, c.course, c.category, c.seats, c.file, c.page, c.line))
        counts = counts_of(parsed, len(parsed.seat_cells), linked)
        cur.execute(
            "INSERT INTO neet.ingest_run (started_at, finished_at, git_commit, input_sha256, counts)"
            " VALUES (%s, %s, %s, %s, %s)",
            (
                started_at,
                datetime.now(UTC),
                git_commit,
                json.dumps({n: e.sha256 for n, e in sorted(manifest.items())}),
                json.dumps(counts),
            ),
        )
    return counts
