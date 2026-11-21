"""The pre-registered Track A rule as a pure function over closing-rank rows (no DB, no LLM).

Rule (eval/golden/questions.yaml, pred-*; scripts/oracle_predict.py):
- eligible allotted categories E = {Open} for General, else {Open, C}; with PwD also "<e> PwD".
- rows come from neet.closing_rank, which already excludes CW / NRI allotments.
- state is the institute's seat-matrix state (neet.institute.state), never address text. With a state
  filter, in-scope institutes without a state are counted as unplaced, never guessed.
- an institute is an option iff some eligible round-K cell for (quota, course) has closing rank >= AIR.
  A cell with no round-K allotment has no row, so it never qualifies.
Every number in an explanation is copied from the row it describes (rank_text, allotments, page, line).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import PurePath

from neet_common.predictor import (
    BestInScope,
    PredictCell,
    PredictOption,
    PredictRequest,
    PredictResponse,
)


@dataclass(frozen=True)
class Row:
    """One neet.closing_rank row joined with its institute and source file."""

    institute_id: int
    institute: str
    state: str | None
    round: int
    quota: str
    course: str
    category: str
    closing_rank: Decimal
    rank_text: str
    allotments: int
    file: str
    page: int
    line: int
    source_sha256: str


def eligible_categories(category: str, pwd: bool) -> list[str]:
    base = ["Open"] if category == "General" else ["Open", category]
    return base + [f"{c} PwD" for c in base] if pwd else base


def file_short(file: str) -> str:
    """Short citation form of a source file: 'r1_allotment_final.pdf' -> 'r1'; otherwise the stem."""
    stem = PurePath(file).stem
    m = re.match(r"(r\d+)_", stem)
    return m.group(1) if m else stem


def cite(r: Row) -> str:
    return f"Source {file_short(r.file)} p{r.page} l{r.line}."


def _allotments(n: int) -> str:
    return f"{n} allotment" if n == 1 else f"{n} allotments"


def _clause(r: Row, rank: int) -> str:
    return (
        f"{r.category} closing rank {r.rank_text} in Round {r.round} ({_allotments(r.allotments)})"
        f" is at or above your AIR {rank}. {cite(r)}"
    )


def _cell(r: Row) -> PredictCell:
    return PredictCell(
        round=r.round,
        quota=r.quota,
        course=r.course,
        category=r.category,
        closing_rank=r.rank_text,
        allotments=r.allotments,
        file=r.file,
        page=r.page,
        line=r.line,
        source_sha256=r.source_sha256,
    )


def predict(rows: list[Row], req: PredictRequest) -> PredictResponse:
    cats = eligible_categories(req.category, req.pwd)
    relevant = [
        r
        for r in rows
        if r.round == req.round and r.quota == req.quota and r.course == req.course and r.category in cats
    ]
    unplaced = 0
    if req.state is not None:
        unplaced = len({r.institute_id for r in relevant if r.state is None})
        relevant = [r for r in relevant if r.state == req.state]
    in_scope = {r.institute_id for r in relevant}

    # Highest closing rank; ties go to PDF order (file, page, line), as in scripts/oracle_predict.py.
    best = min(relevant, key=lambda r: (-r.closing_rank, r.file, r.page, r.line), default=None)

    qualifying: dict[int, list[Row]] = {}
    for r in relevant:
        if r.closing_rank >= req.rank:
            qualifying.setdefault(r.institute_id, []).append(r)

    options: list[tuple[Decimal, str, int, PredictOption]] = []
    for iid, cells in qualifying.items():
        cells.sort(key=lambda r: r.category)
        tightest = min(cells, key=lambda r: (r.closing_rank, r.category))
        first = cells[0]
        opt = PredictOption(
            institute=first.institute,
            institute_id=iid,
            state=first.state,
            best_closing_rank=tightest.rank_text,
            cells=[_cell(r) for r in cells],
            explanation=" ".join(_clause(r, req.rank) for r in cells),
        )
        options.append((tightest.closing_rank, first.institute.lower(), iid, opt))
    options.sort(key=lambda t: t[:3])

    best_out = (
        None
        if best is None
        else BestInScope(
            institute=best.institute,
            category=best.category,
            round=best.round,
            closing_rank=best.rank_text,
            allotments=best.allotments,
            file=best.file,
            page=best.page,
            line=best.line,
            source_sha256=best.source_sha256,
        )
    )
    return PredictResponse(
        inputs=req,
        eligible_categories=cats,
        options=[o for *_, o in options],
        option_count=len(options),
        institutes_in_scope=len(in_scope),
        unplaced_no_state=unplaced,
        best_in_scope=best_out,
        empty_message=None if options else empty_message(req, cats, best, unplaced),
    )


def empty_message(req: PredictRequest, cats: list[str], best: Row | None, unplaced: int) -> str:
    where = f" in {req.state}" if req.state else ""
    if best is None:
        msg = (
            f"No institute{where} had a Round {req.round} allotment for {req.course} under {req.quota}"
            f" in an eligible category ({', '.join(cats)}), so there is no closing rank to compare."
        )
    else:
        msg = (
            f"No institute in scope had an eligible Round {req.round} closing rank at or above your AIR"
            f" {req.rank}. The highest eligible closing rank in scope was {best.rank_text} ({best.category},"
            f" Round {best.round}, {_allotments(best.allotments)}) at {best.institute}. {cite(best)}"
        )
    if unplaced:
        msg += (
            f" {unplaced} institute(s) with eligible allotments have no seat-matrix state and could not be"
            " placed in any state."
        )
    return msg
