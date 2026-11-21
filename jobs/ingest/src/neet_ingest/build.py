"""Parse the verified raw files into the rows ingest loads (pure: no database)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from neet_mccparse.allotments import Allotment, parse_allotments, read_quota_legend
from neet_mccparse.seat_cells import WIDE_LAYOUT_FILES, SeatCell, parse_seat_cells
from neet_mccparse.seat_matrix import (
    LONG_LAYOUT_FILES,
    SeatMatrixInstitute,
    code_of,
    parse_seat_matrix,
    state_of,
)
from neet_mccparse.text import pdftotext_pages, squash

ALLOTMENT_FILES = {1: "r1_allotment_final.pdf", 2: "r2_allotment_final.pdf", 3: "r3_allotment_final.pdf"}
SEAT_MATRIX_FILES = (*LONG_LAYOUT_FILES, *WIDE_LAYOUT_FILES)
# Same rule as scripts/oracle_predict.py (pre-registered): CW / NRI rows are ranked by CW rank or NRI
# priority, not AIR.
CW_NRI_QUOTA = re.compile(r"\(CW\)|CW Quota|Non-Resident Indian")


def is_cw_nri(a: Allotment) -> bool:
    return bool(CW_NRI_QUOTA.search(a.quota)) or "CW Rank" in a.remarks or "NRI Priority" in a.remarks


@dataclass(frozen=True)
class InstituteRow:
    name_norm: str
    display_name: str
    raw_name: str
    state: str | None
    state_source: str | None
    seat_matrix_code: str | None


@dataclass
class Parsed:
    rows_per_round: dict[int, int] = field(default_factory=dict)
    allotments: dict[int, list[Allotment]] = field(default_factory=dict)
    seat_cells: list[SeatCell] = field(default_factory=list)
    institutes: list[InstituteRow] = field(default_factory=list)


def _wide_entries(cells: list[SeatCell]) -> list[SeatMatrixInstitute]:
    seen: dict[str, SeatMatrixInstitute] = {}
    for c in cells:
        if c.file in WIDE_LAYOUT_FILES and c.code not in seen:
            seen[c.code] = SeatMatrixInstitute(c.code, None, c.institute, c.file, c.page)
    return list(seen.values())


def resolve_institutes(
    names: list[str], long_entries: list[SeatMatrixInstitute], wide_entries: list[SeatMatrixInstitute]
) -> list[InstituteRow]:
    """One row per distinct squash(name). State from the long-layout seat matrices only (state_of);
    code from the long layout, else from the wide layout; ambiguous codes stay NULL."""
    first: dict[str, str] = {}
    for n in names:
        first.setdefault(squash(n), n)
    out = []
    for key, raw in sorted(first.items()):
        entry = state_of(raw, long_entries)
        code = code_of(raw, long_entries) if entry is not None else code_of(raw, wide_entries)
        out.append(
            InstituteRow(
                name_norm=key,
                display_name=re.sub(r"\s+", " ", raw).strip(),
                raw_name=raw,
                state=entry.state if entry else None,
                state_source=f"seat_matrix:{entry.file}" if entry else None,
                seat_matrix_code=code,
            )
        )
    return out


def parse_all(paths: dict[str, Path]) -> Parsed:
    out = Parsed()
    for rnd, name in ALLOTMENT_FILES.items():
        res = parse_allotments(paths[name], rnd, strict=True)
        out.rows_per_round[rnd] = res.rows
        out.allotments[rnd] = res.allotments
    quotas = read_quota_legend(pdftotext_pages(paths[ALLOTMENT_FILES[1]], 1, 2))
    long_entries: list[SeatMatrixInstitute] = []
    for name in SEAT_MATRIX_FILES:
        out.seat_cells += parse_seat_cells(paths[name], quotas)
        if name in LONG_LAYOUT_FILES:
            long_entries += parse_seat_matrix(paths[name])
    names = [a.institute for rnd in sorted(out.allotments) for a in out.allotments[rnd]]
    out.institutes = resolve_institutes(names, long_entries, _wide_entries(out.seat_cells))
    return out
