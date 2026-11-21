"""Chunk text for the retrieval index: one 'cell' chunk per closing-rank row, plus 'note' chunks."""

from __future__ import annotations

import re
from pathlib import Path

import psycopg
from neet_mccparse.text import pdftotext_pages
from pydantic import BaseModel

CW_NRI_NOTE = (
    "These seats are allotted by CW rank / NRI priority, not by AIR; the AIR shown is not the admission"
    " cut-off."
)
CELLS_SQL = """
SELECT c.round, c.quota, c.institute_id, c.course, c.allotted_category, c.rank_text, c.allotments,
       c.file, c.page, c.line, i.display_name, i.state
FROM {view} c JOIN neet.institute i ON i.id = c.institute_id
ORDER BY c.round, c.quota, i.name_norm, c.course, c.allotted_category
"""
TABLE_HEADER = re.compile(r"^\s*SNo\s+Rank\b")
PAGE_TITLE = re.compile(r"Seats Allotment -\d{4} Round")
VIEWS = {False: "neet.closing_rank", True: "neet.closing_rank_cw_nri"}  # fixed names, not input


class Chunk(BaseModel):
    kind: str
    text: str
    round: int | None = None
    quota: str | None = None
    institute_id: int | None = None
    course: str | None = None
    allotted_category: str | None = None
    is_cw_nri: bool | None = None
    note: str | None = None
    file: str
    page: int
    line: int | None = None


def cell_text(
    rnd: int, course: str, inst: str, state: str | None, quota: str, cat: str, rank_text: str,
    allotments: int, file: str, page: int, line: int, cw_nri: bool,
) -> str:  # fmt: skip
    where = state if state else "state unknown"
    s = (
        f"NEET-UG 2025, Round {rnd}, {course}, {inst} ({where}), {quota}, allotted category {cat}:"
        f" closing rank {rank_text}, from {allotments} allotment{'s' if allotments != 1 else ''}."
    )
    if cw_nri:
        s += " " + CW_NRI_NOTE
    return s + f" Source: {file} p{page} l{line}."


def cell_chunks(conn: psycopg.Connection) -> list[Chunk]:
    out = []
    for cw, view in VIEWS.items():
        rows = conn.execute(CELLS_SQL.format(view=view)).fetchall()  # view name from the fixed map
        for rnd, quota, iid, course, cat, rank_text, n, file, page, line, name, state in rows:
            text = cell_text(rnd, course, name, state, quota, cat, rank_text, n, file, page, line, cw)
            out.append(
                Chunk(
                    kind="cell", text=text, round=rnd, quota=quota, institute_id=iid, course=course,
                    allotted_category=cat, is_cw_nri=cw, file=file, page=page, line=line,
                )
            )  # fmt: skip
    return out


def _clean(text: str) -> str:
    return re.sub(r"[ \t]+", " ", "\n".join(ln.strip() for ln in text.splitlines() if ln.strip()))


def legend_chunks(r1_pdf: Path) -> list[Chunk]:
    """Quota legend and category legend (R1 pages 1-2), one chunk per page."""
    pages = pdftotext_pages(r1_pdf, 1, 2)
    out = []
    for pno, page in enumerate(pages[:2], 1):
        body = page.split("\n")
        # Keep the legend only: stop at the first allotment table header ("SNo  Rank ...") and drop
        # the page title line ("NEET-UG Counselling Seats Allotment -2025 Round 1") wherever it is.
        stop = next((i for i, ln in enumerate(body) if TABLE_HEADER.search(ln)), len(body))
        body = [ln for ln in body[:stop] if not PAGE_TITLE.search(ln)]
        text = _clean("\n".join(body))
        if text:
            out.append(
                Chunk(kind="note", text=f"Legend, Round 1 allotment result (p{pno}):\n{text}",
                      note=f"r1_legend_p{pno}", file=r1_pdf.name, page=pno)
            )  # fmt: skip
    return out


def notice_chunks(notices: dict[str, Path]) -> list[Chunk]:
    out = []
    for note, pdf in sorted(notices.items()):
        pages = [p for p in pdftotext_pages(pdf) if p.strip()]
        out.append(Chunk(kind="note", text=_clean("\n".join(pages)), note=note, file=pdf.name, page=1))
    return out
