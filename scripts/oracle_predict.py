#!/usr/bin/env python3
"""Independent oracle for the Track A predictor rule (eval/golden/questions.yaml, pred-*).

Rule, written before any predictor code exists:
  inputs: AIR R, candidate category C (+ PwD flag), quota Q, course, round K of 2025, optional state S.
  eligible allotted categories E = {Open} if C = General, else {Open, C}; with PwD, also the PwD
  variant of each (Open PwD, C PwD).
  Excluded from every cell: CW and NRI allotments, i.e. rows in a CW or NRI quota, and rows whose
  remark carries "CW Rank" or "NRI Priority". These are ranked by CW rank / NRI priority, not AIR
  (docs/source_notes.md, decision 4).
  An institute I is a plausible option iff, for some e in E, the round-K closing rank of
  (Q, I, course, e) exists and is >= R. A cell with no allotment in round K never qualifies.
  State S is the seat-matrix StateName of I (oracle_seat_matrix), never address text. With a state
  filter, institutes with no seat-matrix state are reported as unknown, never guessed.

Usage:
  uv run python scripts/oracle_predict.py --round 1 --rank 3000 --category OBC \
      --quota "Open Seat Quota" --course MBBS [--state Karnataka] [--pwd]
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from neet_mccparse.allotments import Allotment, parse_allotments
from neet_mccparse.seat_matrix import SeatMatrixInstitute, load_seat_matrices, state_of
from neet_mccparse.text import squash
from oracle_closing_rank import default_pdf

CW_NRI_QUOTA = re.compile(r"\(CW\)|CW Quota|Non-Resident Indian")
CANDIDATE_CATEGORIES = ("General", "OBC", "EWS", "SC", "ST")


def is_cw_or_nri(a: Allotment) -> bool:
    return bool(CW_NRI_QUOTA.search(a.quota)) or "CW Rank" in a.remarks or "NRI Priority" in a.remarks


def eligible_categories(category: str, pwd: bool) -> tuple[str, ...]:
    if category not in CANDIDATE_CATEGORIES:
        raise ValueError(f"unknown candidate category {category!r}")
    base = ("Open",) if category == "General" else ("Open", category)
    return base + tuple(f"{c} PwD" for c in base) if pwd else base


@dataclass(frozen=True)
class Cell:
    category: str
    closing_rank: Decimal
    rank_text: str
    allotments: int
    page: int
    line: int


@dataclass(frozen=True)
class Option:
    institute: str
    state: str | None
    qualifying: tuple[Cell, ...]


@dataclass(frozen=True)
class Prediction:
    options: list[Option]
    institutes_in_scope: int  # institutes with any eligible-category cell (after the state filter)
    unknown_state: list[str]  # institutes dropped because the seat matrix gives them no state
    max_closing: Cell | None  # highest eligible closing rank in scope (explains an empty result)


def predict(
    allotments: list[Allotment],
    entries: list[SeatMatrixInstitute],
    *,
    rank: Decimal,
    category: str,
    pwd: bool,
    quota: str,
    course: str,
    state: str | None,
) -> Prediction:
    cats = eligible_categories(category, pwd)
    rows: dict[tuple[str, str], list[Allotment]] = {}
    names: dict[str, str] = {}
    for a in allotments:
        if a.quota == quota and a.course == course and a.allotted_category in cats and not is_cw_or_nri(a):
            rows.setdefault((squash(a.institute), a.allotted_category), []).append(a)
            names.setdefault(squash(a.institute), a.institute)
    states: dict[str, str | None] = {}
    unknown: list[str] = []
    for key, name in names.items():
        entry = state_of(name, entries)
        states[key] = entry.state if entry else None
        if state is not None and entry is None:
            unknown.append(name)
    in_scope = {k for k in names if state is None or states[k] == state}
    cells: dict[str, list[Cell]] = {}
    best: Cell | None = None
    for (key, cat), group in rows.items():
        if key not in in_scope:
            continue
        top = max(group, key=lambda a: a.rank)
        cell = Cell(cat, top.rank, top.rank_text, len(group), top.page, top.line)
        if best is None or cell.closing_rank > best.closing_rank:
            best = cell
        if cell.closing_rank >= rank:
            cells.setdefault(key, []).append(cell)
    options = [
        Option(names[k], states[k], tuple(sorted(v, key=lambda c: c.category)))
        for k, v in sorted(cells.items(), key=lambda kv: names[kv[0]].lower())
    ]
    return Prediction(options, len(in_scope), sorted(unknown), best)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Predictor oracle (2025 MCC data)")
    ap.add_argument("--round", type=int, required=True, choices=(1, 2, 3))
    ap.add_argument("--rank", type=Decimal, required=True)
    ap.add_argument("--category", required=True, choices=CANDIDATE_CATEGORIES)
    ap.add_argument("--pwd", action="store_true")
    ap.add_argument("--quota", required=True)
    ap.add_argument("--course", required=True)
    ap.add_argument("--state")
    args = ap.parse_args(argv)
    raw = Path(__file__).resolve().parents[1] / "data/raw/mcc/2025"
    allot = parse_allotments(default_pdf(args.round), args.round).allotments
    pred = predict(
        allot,
        load_seat_matrices(raw),
        rank=args.rank,
        category=args.category,
        pwd=args.pwd,
        quota=args.quota,
        course=args.course,
        state=args.state,
    )
    print(f"options: {len(pred.options)} of {pred.institutes_in_scope} institutes in scope")
    for o in pred.options:
        cells = "; ".join(
            f"{c.category} {c.rank_text} ({c.allotments} allotments, p{c.page} l{c.line})"
            for c in o.qualifying
        )
        print(f"  {o.institute[:70]} [{o.state}] :: {cells}")
    if pred.max_closing is not None:
        m = pred.max_closing
        print(f"highest eligible closing rank in scope: {m.rank_text} ({m.category}, p{m.page} l{m.line})")
    for name in pred.unknown_state:
        print(f"  no seat-matrix state (excluded): {name[:80]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
