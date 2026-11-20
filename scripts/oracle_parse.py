#!/usr/bin/env python3
"""Row parser for MCC NEET-UG allotment PDFs, using ONLY `pdftotext -layout` + regular expressions.

Part of the independent oracle (see oracle_closing_rank.py). Deliberately does not use pdfplumber,
camelot or any PDF library, so it can cross-check the ingest parser.

Layout facts this relies on (verified on the 2025 files, see docs/source_notes.md):
  * every row starts on a line whose first token (indent <= 2) is SNo + Rank (rounds 1-2) or
    Rank (round 3); the first row of each page is preceded by a form feed;
  * the round-N block is the right-most block; its course, categories, option number and remarks
    are anchored by a fixed vocabulary on the row's first line (or second, when a cell is pushed up);
  * earlier-round blocks end in a remark whose first line is one of a few fixed words;
  * wrapped cell text on continuation lines sits within its column, so column zones are set by
    the midpoints between the anchor line's cells.
"""

from __future__ import annotations

import bisect
import itertools
import re
import shutil
import subprocess
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

COURSES = ("MBBS", "BDS", "B.Sc. Nursing")
CATEGORIES = tuple(f"{c}{p}" for c in ("Open", "OBC", "EWS", "SC", "ST") for p in ("", " PwD"))
# Rounds 2 and 3 print "GNYes" where round 1 prints "General PwD"; kept verbatim (see source_notes).
CAND_CATEGORIES = (*(f"{c}{p}" for c in ("General", "OBC", "EWS", "SC", "ST") for p in ("", " PwD")), "GNYes")

_CAT = r"(?:Open|OBC|EWS|SC|ST)(?: PwD)?"
_CCAT = r"(?:(?:General|OBC|EWS|SC|ST)(?: PwD)?|GNYes)"
_COURSE = r"MBBS|BDS|B\.Sc\.(?: Nursing)?"
# Round-N tail on a row's first line, for an allotted row.
TAIL_R1 = re.compile(
    rf"(?<=\s)(?P<course>{_COURSE})\s+(?P<acat>{_CAT})\s+(?P<ccat>{_CCAT})\s+(?P<rem>Allotted.*)$"
)
TAIL_RN = re.compile(
    rf"(?<=\s)(?P<course>{_COURSE})\s+(?P<acat>{_CAT})\s+(?P<ccat>{_CCAT})\s+(?P<opt>\d+)\s+(?P<rem>\S.*)$"
)
# Round-N block of a row with no allotment in this round: quota, institute, course, two categories
# and option number are all "-", then a remark.
EMPTY_RN = re.compile(
    r"(?<=\s)-\s+-\s+-\s+-\s+-\s+-\s+(?P<rem>Did not opt(?: for)?|Did not fill up|No|Not Allotted\.)\s*$"
)
ALLOTTED_WORDS = re.compile(r"Fresh Allotted|Upgraded")
# One earlier-round block on a first line (rounds 2 and 3): four "-" cells, or
# quota + institute + course + remark, where the remark's first line is one of a fixed few words.
PREV_BLOCK = rf"\s*(?:-\s+-\s+-\s+-|.+?\s(?:{_COURSE})\s+(?:Not Reported|Reported|Not|Seat)(?=\s))"
CELL_WRAP = {"course": re.compile("Nursing"), "acat": re.compile("PwD"), "ccat": re.compile("PwD")}
MIN_GLUED_CUT = 3  # a quota glued to the next cell must contribute at least this many characters
FRAG = re.compile(r"\S+(?: \S+)*")  # a run of text; cells are separated by 2+ spaces
QUOTA_LEGEND = re.compile(r"^\s*([A-Z]{2})\s{3,}(\S.*?)\s*$")
RANK = r"\d+(?:\.\d+)?"


class OracleError(RuntimeError):
    """The text layout did not match what the oracle expects."""


@dataclass(frozen=True)
class Allotment:
    file: str
    page: int
    line: int  # 1-based line number of the row's first line within the page's pdftotext output
    rank: Decimal
    rank_text: str
    quota: str
    institute: str
    course: str
    allotted_category: str
    candidate_category: str
    remarks: str


@dataclass(frozen=True)
class ParseResult:
    rows: int  # every candidate row in the file
    allotments: list[Allotment]  # rows with an allotment in this round
    quotas: tuple[str, ...]  # quota descriptions from the file's own legend
    failures: list[str]  # rows that could not be parsed (only when strict=False)


def squash(text: str) -> str:
    """Lower-case, all whitespace removed: makes matching immune to line wraps inside words."""
    return re.sub(r"\s+", "", text).lower()


def pdftotext_pages(pdf: Path) -> list[str]:
    exe = shutil.which("pdftotext")
    if exe is None:
        raise OracleError("pdftotext not found (brew install poppler)")
    out = subprocess.run(  # noqa: S603 - fixed executable, list args, no shell
        [exe, "-layout", str(pdf), "-"], check=True, capture_output=True, text=True
    ).stdout
    return out.split("\f")


def read_quota_legend(pages: list[str]) -> tuple[str, ...]:
    quotas: list[str] = []
    for line in "\n".join(pages[:2]).split("\n"):
        m = QUOTA_LEGEND.match(line)
        if m and m.group(1) not in ("BC", "EW", "GN", "SC", "ST"):
            quotas.append(m.group(2))
    # Legend descriptions can wrap (round 2: "...(CW) DU" / "Quota"); the wrapped tail is a line
    # with no code and at most two words. Re-join those (but not the next section's heading).
    text = "\n".join(pages[:2])
    for short in list(quotas):
        m = re.search(re.escape(short) + r"\n\s{20,}(\S+(?: \S+)?)\s*\n", text)
        if m and "Abbrevation" not in m.group(1) and not QUOTA_LEGEND.match(m.group(0).split("\n")[1]):
            quotas[quotas.index(short)] = f"{short} {m.group(1)}"
    if len(quotas) < 20:
        raise OracleError(f"quota legend not found (got {len(quotas)})")
    return tuple(quotas)


def _frags(line: str) -> list[tuple[int, int, str]]:
    return [(m.start(), m.end(), m.group()) for m in FRAG.finditer(line)]


def _is_quota_prefix(text: str, squashed_quotas: tuple[str, ...]) -> bool:
    s = squash(text)
    return bool(s) and any(q.startswith(s) for q in squashed_quotas)


Frag = tuple[int, int, str]


def _split_quota_words(
    frag: Frag, prefix: str, squashed_quotas: tuple[str, ...], *, need_tail: bool
) -> tuple[Frag | None, Frag | None]:
    """Split the leading words off `frag` that extend `prefix` towards a known quota name.

    Returns (quota_part, rest). With need_tail, at least one word is left in `rest`.
    """
    start, end, text = frag
    words = text.split(" ")
    best = 0
    for k in range(1, len(words) + (0 if need_tail else 1)):
        if _is_quota_prefix(prefix + " ".join(words[:k]), squashed_quotas):
            best = k
    head = " ".join(words[:best])
    tail = " ".join(words[best:])
    if tail:
        # Cells can be glued with no space at all ("Internal -PuducherryJIPMER", "ResidentMedical"):
        # extend into the next word character by character while it still extends a quota name.
        joined = prefix + head + (" " if head else "")
        cut = max(
            (
                c
                for c in range(MIN_GLUED_CUT, len(words[best]))
                if _is_quota_prefix(joined + tail[:c], squashed_quotas)
            ),
            default=0,
        )
        if cut:
            head = (head + " " if head else "") + tail[:cut]
            tail = tail[cut:]
    if not head:
        return None, frag
    if not tail:
        return frag, None
    return (start, start + len(head), head), (end - len(tail), end, tail)


Anchor = tuple[int, int, str, str]  # (start, end, text, role)


def _tail_anchors(m: re.Match[str]) -> list[Anchor]:
    return [
        (m.start(r), m.end(r), m.group(r), r)
        for r in ("course", "acat", "ccat", "opt", "rem")
        if m.groupdict().get(r) is not None
    ]


def _split_anchors(above: str, first: str, m: re.Match[str], round_no: int) -> list[Anchor]:
    """Anchor cells spread over two lines: earlier blocks + round-N quota on the line above, the
    round-N institute and tail on the next ("- - - - Jain Minority" / "SBKS Med. Inst. ...")."""
    prev = re.match(PREV_BLOCK * (round_no - 1), above)
    if prev is None:
        raise OracleError(f"earlier-round block(s) not recognised: {above.strip()[:160]!r}")
    others = [f for f in _frags(above) if f[1] <= prev.end()]
    quota = [f for f in _frags(above) if f[0] >= prev.end()]
    inst = _frags(first[: m.start("course")])
    if not quota or not inst:
        raise OracleError(f"two-line anchor not recognised: {above.strip()[:80]!r} / {first.strip()[:80]!r}")
    anchors: list[Anchor] = [(*f, "other") for f in others]
    anchors.append((quota[0][0], quota[-1][1], " ".join(f[2] for f in quota), "quota"))
    anchors.append((inst[0][0], inst[-1][1], " ".join(f[2] for f in inst), "inst"))
    return sorted(anchors + _tail_anchors(m))


def _first_line_anchors(
    first: str, m: re.Match[str], round_no: int, sq_quotas: tuple[str, ...], above: str | None = None
) -> list[Anchor]:
    """Cells of the anchor line: earlier-round cells ("other"), then round-N quota, institute, tail."""
    left_text = first[: m.start("course")]
    prev = re.match(PREV_BLOCK * (round_no - 1), left_text)
    if prev is None and above is not None:
        return _split_anchors(above, first, m, round_no)
    if prev is None:
        raise OracleError(f"earlier-round block(s) not recognised: {first.strip()[:160]!r}")
    cut = prev.end()
    others: list[Frag] = []
    block: list[Frag] = []
    for f in _frags(left_text):
        if f[1] <= cut:
            others.append(f)
        elif f[0] >= cut:
            block.append(f)
        else:  # glued across the boundary, e.g. "Reported Deemed/Paid JSS"
            after = first[cut : f[1]].lstrip()
            others.append((f[0], cut, first[f[0] : cut].rstrip()))
            block.append((f[1] - len(after), f[1], after))
    if not block:
        raise OracleError(f"no round-N quota/institute cells: {first.strip()[:160]!r}")
    if len(block) >= 2 and _is_quota_prefix(block[0][2], sq_quotas):
        quota, rest = block[0], block[1:]
    else:
        quota, inst_head = _split_quota_words(block[0], "", sq_quotas, need_tail=True)
        if quota is None or inst_head is None:
            raise OracleError(f"cannot find round-N quota on: {first.strip()[:160]!r}")
        rest = [inst_head, *block[1:]]
    inst = (rest[0][0], rest[-1][1], " ".join(f[2] for f in rest))
    anchors: list[Anchor] = [(*f, "other") for f in others]
    anchors += [(*quota, "quota"), (*inst, "inst")]
    return sorted(anchors + _tail_anchors(m))


def _zone_pieces(frag: Frag, anchors: list[Anchor]) -> list[tuple[str, Frag]]:
    """Assign a continuation fragment to the column zones set by the anchor line.

    Zone boundaries sit midway between neighbouring anchor cells. A fragment inside one zone goes
    there whole; a fragment that crosses a boundary is split word by word.
    """
    bounds = [(a[1] + b[0]) / 2 for a, b in itertools.pairwise(anchors)]

    def zone(x: float) -> str:
        return anchors[bisect.bisect_left(bounds, x)][3]

    s, e, text = frag
    if zone(s) == zone(e - 1):
        return [(zone((s + e) / 2), frag)]
    pieces: list[tuple[str, Frag]] = []
    for w in re.finditer(r"\S+", text):
        ws, we = s + w.start(), s + w.end()
        role = zone((ws + we) / 2)
        if pieces and pieces[-1][0] == role:
            ps, _, pt = pieces[-1][1]
            pieces[-1] = (role, (ps, we, f"{pt} {w.group()}"))
        else:
            pieces.append((role, (ws, we, w.group())))
    return pieces


def _parse_row(lines: list[str], round_no: int, sq_quotas: tuple[str, ...]) -> dict[str, str] | None:
    """Return the round-N fields of one row, or None if the row has no allotment this round."""
    tail_re = TAIL_R1 if round_no == 1 else TAIL_RN
    # The tail is on the row's first line, or (when a cell is pushed up a line) on the second.
    found: tuple[int, re.Match[str]] | None = None
    for idx, line in enumerate(lines[:2]):
        if (m := tail_re.search(line)) is not None:
            found = (idx, m)
            break
        if EMPTY_RN.search(line):
            if any(ALLOTTED_WORDS.search(x) for x in lines):
                raise OracleError(f"row looks empty but mentions an allotment: {line.strip()[:160]!r}")
            return None
    if found is None:
        raise OracleError(f"row tail not recognised: {lines[0].strip()[:160]!r}")
    ai, m = found
    above = lines[0] if ai == 1 and lines[0].strip() else None
    anchors = _first_line_anchors(lines[ai], m, round_no, sq_quotas, above)
    two_line = above is not None and any(a[3] == "quota" and a[2] in above for a in anchors)
    parts: dict[str, list[str]] = {a[3]: [] for a in anchors if a[3] != "other"}
    for idx, line in enumerate(lines):
        if two_line and idx == 0:
            continue
        if idx == ai:
            for a in anchors:
                if a[3] != "other":
                    parts[a[3]].append(a[2])
            continue
        for frag in _frags(line):
            for role, piece in _zone_pieces(frag, anchors):
                if role in ("quota", "inst"):
                    # Quota and institute cells can touch with one space between them. Leading
                    # words go to the quota only while they extend a real quota name.
                    head, rest = _split_quota_words(
                        piece, " ".join(parts["quota"]), sq_quotas, need_tail=False
                    )
                    if head is not None:
                        parts["quota"].append(head[2])
                    if rest is not None:
                        parts["inst"].append(rest[2])
                elif role in ("course", "acat", "ccat", "opt"):
                    # These cells only ever wrap as "B.Sc." / "Nursing" or "<cat>" / "PwD". Anything
                    # else here is a wide institute line spilling right.
                    if CELL_WRAP.get(role, re.compile("$^")).fullmatch(piece[2]):
                        parts[role].append(piece[2])
                    else:
                        parts["inst"].append(piece[2])
                elif role == "rem":
                    parts[role].append(piece[2])
    return {k: " ".join(v) for k, v in parts.items()}


def _canon(value: str, vocab: tuple[str, ...], what: str) -> str:
    for v in vocab:
        if squash(v) == squash(value):
            return v
    raise OracleError(f"unknown {what}: {value!r}")


def parse_allotments(pdf: Path, round_no: int, *, strict: bool = True) -> ParseResult:
    """Parse one allotment PDF (round 1, 2 or 3) via `pdftotext -layout`."""
    return parse_pages(pdftotext_pages(pdf), pdf.name, round_no, strict=strict)


def parse_pages(pages: list[str], file_name: str, round_no: int, *, strict: bool = True) -> ParseResult:
    """Parse the `pdftotext -layout` text of an allotment PDF, one string per page."""
    quotas = read_quota_legend(pages)
    sq_quotas = tuple(squash(q) for q in quotas)
    start_re = re.compile(rf"^ {{0,2}}\d+\s+({RANK})(?=\s)" if round_no < 3 else rf"^ {{0,2}}({RANK})(?=\s)")
    rows: list[tuple[int, int, str, list[str]]] = []
    for pno, page in enumerate(pages, 1):
        current: list[str] | None = None
        for lno, line in enumerate(page.split("\n"), 1):
            m = start_re.match(line)
            if m:
                current = [" " * m.end() + line[m.end() :]]  # blank SNo/rank so they are not cells
                rows.append((pno, lno, m.group(1), current))
            elif current is not None and line.strip() and "Page No." not in line:
                current.append(line)
    ranks = [Decimal(r[2]) for r in rows]
    if any(b <= a for a, b in itertools.pairwise(ranks)):
        raise OracleError("ranks are not strictly increasing: row segmentation is wrong")
    allotments: list[Allotment] = []
    failures: list[str] = []
    for pno, lno, rank_text, lines in rows:
        try:
            f = _parse_row(lines, round_no, sq_quotas)
            if f is None:
                continue
            allotments.append(
                Allotment(
                    file=file_name,
                    page=pno,
                    line=lno,
                    rank=Decimal(rank_text),
                    rank_text=rank_text,
                    quota=_canon(f["quota"], quotas, "quota"),
                    institute=re.sub(r"\s+", " ", f["inst"]).strip(),
                    course=_canon(f["course"], COURSES, "course"),
                    allotted_category=_canon(f["acat"], CATEGORIES, "allotted category"),
                    candidate_category=_canon(f["ccat"], CAND_CATEGORIES, "candidate category"),
                    remarks=re.sub(r"\s+", " ", f["rem"]).strip(),
                )
            )
        except OracleError as exc:
            msg = f"{file_name} p{pno} l{lno} rank {rank_text}: {exc}"
            if strict:
                raise OracleError(msg) from exc
            failures.append(msg + "\n" + "\n".join(lines))
    return ParseResult(rows=len(rows), allotments=allotments, quotas=quotas, failures=failures)
