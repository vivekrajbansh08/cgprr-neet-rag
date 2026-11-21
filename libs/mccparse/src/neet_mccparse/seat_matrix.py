"""Institute -> state from the MCC Round 1 seat matrices, using ONLY `pdftotext -layout` + regex.

Used by the independent oracle and by jobs/ingest. The state comes from the seat matrix
**StateName** column, never from address text in the allotment PDFs (docs/source_notes.md, decision 6).

Long-layout seat matrices (AIQ except CU, AIIMS/BHU/JIPMER, central universities) print one record
per institute x quota x course x category. Layout facts:
  * the record's "seat line" ends with branch + category + seats ("MBBS (MBBS)  OP NO  48"), and
    starts with StateName;
  * the institute cell (name + address) spans the lines around it and ends with a 6-digit
    institute code in parentheses, "(200631)";
  * the InstituteType cell sits between StateName and the institute, possibly wrapped, and the quota
    cell sits right of the institute.
Wide-layout matrices (deemed universities, ESIC IP) have no StateName column. Their institutes
get no state from this module.

Allotment institutes have no code. They are matched to a seat-matrix entry by the longest common
prefix of the normalised (lower-case, whitespace-free) strings. A tie between entries in different
states is an error, never a guess.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from neet_mccparse.text import OracleError, pdftotext_pages, squash

SEAT_LINE = re.compile(
    r"(?P<branch>(?:MBBS|BDS) \((?:MBBS|BDS)\))\s+(?P<cat>[A-Z]{2} (?:NO|PH))\s+(?P<seats>\d+)\s*$"
)
CODE = re.compile(r"\((\d{6})\)")
STATE_AT_START = re.compile(r"^\s*(\S+(?: \S+)*?)(?=\s{2,}|$)")
NOISE = re.compile(r"Page \d+ of \d+|SEAT MATRIX|StateName")
# InstituteType cell fragments, normalised; at most one is stripped from the start of each line.
TYPE_FRAGMENTS = tuple(
    sorted(
        (
            "allindiaexceptcentraluniversity",
            "allindiaexceptcentral",
            "allindiainstituteofmedicalscience(aiims)",
            "allindiainstituteofmedical",
            "science(aiims)",
            "centraluniversity",
            "employeesstateinsurancescheme",
            "employeesstateinsurance",
            "university",
            "scheme",
            "jawaharlalinstituteofpostgraduate",
            "medicaleducationandresearch",
        ),
        key=len,
        reverse=True,
    )
)
MIN_PREFIX = 20  # an allotment matches a seat-matrix entry only if this many leading chars agree
LONG_LAYOUT_FILES = (
    "seat_matrix_r1_aiq_except_cu.pdf",
    "seat_matrix_r1_aiims_bhu_jipmer.pdf",
    "seat_matrix_r1_central_universities.pdf",
)


@dataclass(frozen=True)
class SeatMatrixInstitute:
    code: str
    state: str | None  # None for wide-layout matrices (no StateName column)
    name: str  # normalised institute cell text (name + address), squashed
    file: str
    page: int


def _institute_text(lines: list[str], x_cut: int, state: str) -> str:
    parts = []
    for line in lines:
        s = squash(CODE.sub("", line[:x_cut]))
        if s.startswith(squash(state)):
            s = s[len(squash(state)) :]
        for frag in TYPE_FRAGMENTS:
            if s.startswith(frag):
                s = s[len(frag) :]
                break
        parts.append(s)
    return "".join(parts)


def _quota_column(page: str) -> int | None:
    """Left edge of the quota column on a page.

    It is the leftmost start of a quota cell printed on a seat line. Cells holding an institute
    code are skipped (institute glued to the quota), and so are lines whose only left cell is the
    state (quota printed above or below).
    """
    starts = []
    for line in page.split("\n"):
        m = SEAT_LINE.search(line)
        if m is None:
            continue
        cells = list(re.finditer(r"\S+(?: \S+)*", line[: m.start()]))
        if len(cells) >= 2 and not CODE.search(cells[-1].group()):
            starts.append(cells[-1].start())
    return min(starts) if starts else None


def long_records(file_name: str, pno: int, page: str) -> list[tuple[int, SeatMatrixInstitute]]:
    """Every record on one long-layout page: (1-based line number of its seat line, institute)."""
    x_quota = _quota_column(page)
    if x_quota is None:
        return []  # no records on this page
    out: list[tuple[int, SeatMatrixInstitute]] = []
    pending: list[tuple[int, str]] = []
    for lno, line in enumerate(page.split("\n"), 1):
        if not line.strip() or NOISE.search(line):
            continue
        pending.append((lno, line))
        code = CODE.search(line)
        seat_lines = [(n, ln) for n, ln in pending if SEAT_LINE.search(ln)]
        if code is None or not seat_lines:
            continue
        if len(seat_lines) != 1:
            raise OracleError(f"{file_name} p{pno}: {len(seat_lines)} seat lines in one record")
        seat_no, seat = seat_lines[0]
        x_cut = x_quota
        if code.start() >= x_cut:
            # Institute glued to the quota cell by one space: "... Sindhudurg (200587) All India".
            x_cut = code.end()
        sm = STATE_AT_START.match(seat)
        if sm is None or sm.start(1) > 6:
            raise OracleError(f"{file_name} p{pno}: no StateName at the start of {seat.strip()[:80]!r}")
        state = sm.group(1)
        text = _institute_text([ln for _, ln in pending], x_cut, state)
        out.append((seat_no, SeatMatrixInstitute(code.group(1), state, text, file_name, pno)))
        pending = []
    return out


def parse_seat_matrix(pdf: Path) -> list[SeatMatrixInstitute]:
    """One entry per (code, state) found in a long-layout seat matrix."""
    found: dict[str, SeatMatrixInstitute] = {}
    for pno, page in enumerate(pdftotext_pages(pdf), 1):
        for _, entry in long_records(pdf.name, pno, page):
            prev = found.get(entry.code)
            if prev is not None and prev.state != entry.state:
                raise OracleError(f"institute {entry.code} listed under {prev.state} and {entry.state}")
            if prev is None or len(entry.name) > len(prev.name):
                found[entry.code] = entry
    return list(found.values())


def load_seat_matrices(raw_dir: Path) -> list[SeatMatrixInstitute]:
    entries: list[SeatMatrixInstitute] = []
    for name in LONG_LAYOUT_FILES:
        entries += parse_seat_matrix(raw_dir / name)
    return entries


def _common_prefix(a: str, b: str) -> int:
    n = 0
    for x, y in zip(a, b, strict=False):
        if x != y:
            break
        n += 1
    return n


CITY_CHARS = 8  # how much of the second comma-separated part (usually the city) must also agree


def required_prefix(institute: str) -> int:
    """How much of an allotment string a match must cover: the whole first comma-separated part
    (the name) plus the first CITY_CHARS characters of the second (usually the city), e.g.
    "governmentmedicalcollege,jaisalme". A shorter overlap ("governmentmedicalcollege,") is generic
    and proves nothing. Seat-matrix text can carry stray glued characters further along, so no more
    than this is required."""
    parts = squash(institute).split(",")
    need = len(parts[0]) + (1 + min(len(parts[1]), CITY_CHARS) if len(parts) > 1 else 0)
    return max(MIN_PREFIX, need)


def best_matches(institute: str, entries: list[SeatMatrixInstitute]) -> list[SeatMatrixInstitute]:
    """Entries tied for the longest common prefix with an allotment institute string, or [] if
    none covers its name + city (required_prefix)."""
    key = squash(institute)
    need = min(required_prefix(institute), len(key))
    scored = sorted(((_common_prefix(key, e.name), e) for e in entries), key=lambda t: -t[0])
    if not scored or scored[0][0] < need:
        return []
    best = scored[0][0]
    return [e for score, e in scored if score == best]


def state_of(institute: str, entries: list[SeatMatrixInstitute]) -> SeatMatrixInstitute | None:
    """The seat-matrix entry for an allotment institute string, or None if no entry covers its
    name + city. Raises if equally good entries disagree on the state."""
    tied = best_matches(institute, entries)
    if not tied:
        return None
    states = {e.state for e in tied}
    if len(states) > 1:
        raise OracleError(
            f"institute {institute[:60]!r} matches seat-matrix entries in states {sorted(states)}"
        )
    return tied[0]


def code_of(institute: str, entries: list[SeatMatrixInstitute]) -> str | None:
    """The seat-matrix institute code for an allotment institute string, or None when no entry
    matches or equally good entries carry different codes (never a guess)."""
    codes = {e.code for e in best_matches(institute, entries)}
    return codes.pop() if len(codes) == 1 else None
