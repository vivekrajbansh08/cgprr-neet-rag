"""Cell-level seat counts from the MCC Round 1 seat matrices (`pdftotext -layout` + regex).

One SeatCell per institute x quota x course x allotted category, with the category and quota in the
vocabulary of the allotment PDFs (quota names from the allotment legend, categories as in
allotments.CATEGORIES).

Long layout (AIQ except CU, AIIMS/BHU/JIPMER, central universities): one record per seat line
("MBBS (MBBS)  OP NO  48"); category codes OP/BC/EW/SC/ST and NO (non-PwD) / PH (PwD). The quota
cell sits left of the branch and can wrap over the lines above and below the seat line, be glued to
the institute text by one space, or be printed entirely above/below a seat line that carries none.
Wide layout (deemed, ESIC IP): one line per institute x quota with 10 category columns + total and
no StateName.

Quota text is assembled from the quota column and must equal a legend quota name exactly (after
squash); anything unknown or ambiguous raises. Nothing is guessed.
"""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass
from pathlib import Path

from neet_mccparse.seat_matrix import CODE, NOISE, SEAT_LINE, TYPE_FRAGMENTS, long_records
from neet_mccparse.text import OracleError, pdftotext_pages, squash

CATEGORY_CODES = {"OP": "Open", "BC": "OBC", "EW": "EWS", "SC": "SC", "ST": "ST"}
PWD_CODES = {"NO": "", "PH": " PwD"}
WIDE_COLUMNS = (
    "Open",
    "Open PwD",
    "EWS",
    "EWS PwD",
    "OBC",
    "OBC PwD",
    "SC",
    "SC PwD",
    "ST",
    "ST PwD",
)
WIDE_LINE = re.compile(
    r"^(?P<left>.*?)(?<=\s)(?P<prog>MBBS|BDS)(?=\s)(?P<quota>.*?)(?P<nums>(?:\s+\d+){11})\s*$"
)
WIDE_HEADER = re.compile(r"Page \d+ of \d+|SEAT MATRIX|Institute Type|General-|^\s*EWS\s+EWS PwD\s*$")
WIDE_TYPE_MAX_X = 12  # wide layout: cells starting left of this are the InstituteType column
COLUMN_SLACK = 2  # a quota-column cell may start this many characters left of the column edge
MAX_COMBINATIONS = 5000
FRAG = re.compile(r"\S+(?: \S+)*")


@dataclass(frozen=True)
class SeatCell:
    code: str
    state: str | None  # seat-matrix StateName; None in the wide layout
    institute: str  # squashed institute cell text (name + address), as in SeatMatrixInstitute.name
    quota: str  # allotment legend name
    course: str  # MBBS | BDS
    category: str  # allotted category, allotment vocabulary ("Open PwD")
    seats: int
    file: str
    page: int
    line: int  # 1-based line of the seat line / data line in the page's pdftotext output


def category_of(code: str) -> str:
    """'OP PH' -> 'Open PwD'. Raises on an unknown code."""
    parts = code.split()
    if len(parts) != 2 or parts[0] not in CATEGORY_CODES or parts[1] not in PWD_CODES:
        raise OracleError(f"unknown seat-matrix category code {code!r}")
    return CATEGORY_CODES[parts[0]] + PWD_CODES[parts[1]]


def _line_options(line: str, end: int, x_col: int) -> list[str]:
    """Possible quota-column contributions of one line (squashed). Cells starting in the column are
    fixed; a cell that starts left of it but reaches into it (quota glued to the institute) may
    contribute any trailing run of its words, including none."""
    fixed: list[str] = []
    glued: list[str] = [""]
    for f in FRAG.finditer(line[:end]):
        if f.start() >= x_col - COLUMN_SLACK:
            fixed.append(f.group())
        elif f.end() > x_col:
            words = f.group().split(" ")
            glued = ["", *(" ".join(words[k:]) for k in range(len(words)))]
    tail = squash(" ".join(fixed))
    return sorted({squash(g) + tail for g in glued})


def _resolve_quota(options: list[list[str]], centre: int, vocab: dict[str, str], where: str) -> str:
    """The one legend quota spelt by a contiguous run of lines that contains the centre line."""
    found: set[str] = set()
    for a in range(centre + 1):
        for b in range(centre, len(options)):
            run = options[a : b + 1]
            n = 1
            for o in run:
                n *= len(o)
            if n > MAX_COMBINATIONS:
                raise OracleError(f"{where}: quota column too ambiguous ({n} combinations)")
            for combo in itertools.product(*run):
                text = "".join(combo)
                if text in vocab:
                    found.add(vocab[text])
    if len(found) != 1:
        raise OracleError(f"{where}: quota not recognised (candidates {sorted(found)})")
    return found.pop()


def _quota_vocab(quotas: tuple[str, ...]) -> dict[str, str]:
    return {squash(q): q for q in quotas}


def _quota_x(lines: list[str], vocab: dict[str, str]) -> int | None:
    """Left edge of the long-layout quota column: leftmost seat-line cell that starts a quota name."""
    starts = []
    for line in lines:
        m = SEAT_LINE.search(line)
        if m is None:
            continue
        cells = list(FRAG.finditer(line[: m.start()]))
        if cells and any(k.startswith(squash(cells[-1].group())) for k in vocab):
            starts.append(cells[-1].start())
    return min(starts) if starts else None


def parse_long_page(file_name: str, pno: int, page: str, quotas: tuple[str, ...]) -> list[SeatCell]:
    records = dict(long_records(file_name, pno, page))
    if not records:
        return []
    vocab = _quota_vocab(quotas)
    lines = page.split("\n")
    x_col = _quota_x(lines, vocab)
    if x_col is None:
        raise OracleError(f"{file_name} p{pno}: quota column not found")
    seat_nos = sorted(records)
    cells: list[SeatCell] = []
    for k, sno in enumerate(seat_nos):
        lo = seat_nos[k - 1] + 1 if k else 1
        hi = seat_nos[k + 1] - 1 if k + 1 < len(seat_nos) else len(lines)
        window = [n for n in range(lo, hi + 1) if lines[n - 1].strip() and not NOISE.search(lines[n - 1])]
        options = []
        for n in window:
            m = SEAT_LINE.search(lines[n - 1])
            options.append(_line_options(lines[n - 1], m.start() if m else len(lines[n - 1]), x_col))
        where = f"{file_name} p{pno} l{sno}"
        quota = _resolve_quota(options, window.index(sno), vocab, where)
        m = SEAT_LINE.search(lines[sno - 1])
        if m is None:
            raise OracleError(f"{where}: seat line lost")
        inst = records[sno]
        cells.append(
            SeatCell(
                code=inst.code,
                state=inst.state,
                institute=inst.name,
                quota=quota,
                course=m.group("branch").split(" ")[0],
                category=category_of(m.group("cat")),
                seats=int(m.group("seats")),
                file=file_name,
                page=pno,
                line=sno,
            )
        )
    return cells


def _wide_institute(lines: list[str], x_end: int) -> str:
    parts = []
    for line in lines:
        for f in FRAG.finditer(line[:x_end]):
            if f.start() >= WIDE_TYPE_MAX_X:
                parts.append(squash(CODE.sub("", f.group())))
    text = "".join(parts)
    for frag in (*TYPE_FRAGMENTS, "deemeduniversity"):
        if text.startswith(frag):
            return text[len(frag) :]
    return text


def parse_wide_page(file_name: str, pno: int, page: str, quotas: tuple[str, ...]) -> list[SeatCell]:
    vocab = _quota_vocab(quotas)
    lines = page.split("\n")
    data = [n for n, ln in enumerate(lines, 1) if WIDE_LINE.match(ln) and not WIDE_HEADER.search(ln)]
    cells: list[SeatCell] = []
    prev = max(
        (n for n, ln in enumerate(lines, 1) if WIDE_HEADER.search(ln) and (not data or n < data[0])),
        default=0,
    )
    for dno in data:
        m = WIDE_LINE.match(lines[dno - 1])
        if m is None:
            raise OracleError(f"{file_name} p{pno} l{dno}: data line lost")
        where = f"{file_name} p{pno} l{dno}"
        record = [n for n in range(prev + 1, dno + 1) if lines[n - 1].strip()]
        x_col = m.end("prog") + 1
        options = [
            _line_options(lines[n - 1], m.start("nums") if n == dno else len(lines[n - 1]), x_col)
            for n in record
        ]
        quota = _resolve_quota(options, len(record) - 1, vocab, where)
        codes = {c for n in record for c in CODE.findall(lines[n - 1])}
        if len(codes) != 1:
            raise OracleError(f"{where}: expected one institute code, found {sorted(codes)}")
        nums = [int(x) for x in m.group("nums").split()]
        if sum(nums[:10]) != nums[10]:
            raise OracleError(f"{where}: category seats {nums[:10]} do not add up to total {nums[10]}")
        inst = _wide_institute([lines[n - 1] for n in record], m.start("prog"))
        code = codes.pop()
        for cat, seats in zip(WIDE_COLUMNS, nums[:10], strict=True):
            if seats:
                cells.append(
                    SeatCell(code, None, inst, quota, m.group("prog"), cat, seats, file_name, pno, dno)
                )
        prev = dno
    return cells


WIDE_LAYOUT_FILES = ("seat_matrix_r1_deemed.pdf", "seat_matrix_r1_esic_ip.pdf")


def parse_seat_cells(pdf: Path, quotas: tuple[str, ...]) -> list[SeatCell]:
    """Every non-zero seat cell of one Round 1 seat matrix (long or wide layout by file name)."""
    wide = pdf.name in WIDE_LAYOUT_FILES
    out: list[SeatCell] = []
    for pno, page in enumerate(pdftotext_pages(pdf), 1):
        parse = parse_wide_page if wide else parse_long_page
        out += parse(pdf.name, pno, page, quotas)
    return out
