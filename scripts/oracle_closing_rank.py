#!/usr/bin/env python3
"""Oracle CLI: closing rank from an MCC NEET-UG allotment PDF.

Method: `pdftotext -layout` plus regular expressions, via the shared parser package
`neet_mccparse`. Ingest uses the SAME parser (decision 2026-11-21), so this CLI no longer
cross-checks parsing; see docs/source_notes.md section 7 for the independent evidence (seat-matrix
and keyword reconciliation, eye checks, PDF re-extraction).

Closing rank = the highest (numerically largest) AIR among rows that received an allotment IN THIS
ROUND for the given quota x institute x course x allotted category. Rows that only carry a seat
from an earlier round ("Did not opt for Upgradation", "No Upgradation", "-" in the round-N block)
are not allotments in round N and are excluded. See docs/source_notes.md.

Known divergence from the database: this CLI counts ALL allotments in the cell, including CW/NRI
rows (CW/NRI quota, or a "CW Rank" / "NRI Priority" remark). The view neet.closing_rank excludes
them, and neet.closing_rank_cw_nri holds them separately. In 2025, 16 cells mix both kinds; for
those cells this CLI and the view differ. No golden question uses such a cell. Derive any new golden
value for one of them from the views, or state the divergence explicitly.

Usage:
  uv run python scripts/oracle_closing_rank.py --round 1 --quota "Open Seat Quota" \
      --institute "Maulana Azad Medical College" --course MBBS --category Open
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from neet_mccparse.allotments import CATEGORIES, COURSES, Allotment, parse_allotments
from neet_mccparse.text import OracleError, squash


class AmbiguousInstituteError(OracleError):
    """The institute substring matches more than one institute among the filtered rows."""

    def __init__(self, institutes: list[str]) -> None:
        super().__init__(f"institute substring matches {len(institutes)} institutes: {institutes}")
        self.institutes = institutes


@dataclass(frozen=True)
class ClosingRank:
    closing_rank: Decimal | None
    matches: int
    row: Allotment | None  # the row that sets the closing rank


def closing_rank(
    allotments: list[Allotment], quota: str, institute: str, course: str, category: str
) -> ClosingRank:
    """Highest rank allotted in this round for the cell. Refuses to pool two institutes."""
    hits = [
        a
        for a in allotments
        if squash(a.quota) == squash(quota)
        and squash(institute) in squash(a.institute)
        and a.course == course
        and a.allotted_category == category
    ]
    if not hits:
        return ClosingRank(None, 0, None)
    institutes = sorted({squash(a.institute) for a in hits})
    if len(institutes) > 1:
        raise AmbiguousInstituteError(sorted({a.institute for a in hits}))
    top = max(hits, key=lambda a: a.rank)
    return ClosingRank(top.rank, len(hits), top)


def default_pdf(round_no: int) -> Path:
    return Path(__file__).resolve().parents[1] / "data/raw/mcc/2025" / f"r{round_no}_allotment_final.pdf"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--round", type=int, required=True, choices=(1, 2, 3))
    ap.add_argument("--quota", required=True, help='full quota name, e.g. "Open Seat Quota"')
    ap.add_argument("--institute", required=True, help="substring of institute name (wrap-insensitive)")
    ap.add_argument("--course", required=True, choices=COURSES)
    ap.add_argument("--category", required=True, choices=CATEGORIES, help="allotted category")
    ap.add_argument("--pdf", type=Path, help="override the allotment PDF path")
    args = ap.parse_args(argv)
    pdf = args.pdf or default_pdf(args.round)
    res = parse_allotments(pdf, args.round)
    try:
        cr = closing_rank(res.allotments, args.quota, args.institute, args.course, args.category)
    except AmbiguousInstituteError as exc:
        print("closing_rank: AMBIGUOUS (use a longer --institute substring)")
        for name in exc.institutes:
            print(f"  candidate: {name}")
        return 2
    if cr.row is None:
        print(f"closing_rank: NONE  matches: 0  (file: {pdf.name}, rows parsed: {res.rows})")
        return 1
    print(f"closing_rank: {cr.row.rank_text}")
    print(f"matches: {cr.matches}")
    print(f"source: {cr.row.file} page {cr.row.page} line {cr.row.line}")
    print(f"institute: {cr.row.institute}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
