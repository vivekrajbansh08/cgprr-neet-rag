"""Citation verifier (project rule b). Pure code: no LLM, no I/O. Never weaken it to pass an eval.

Shared by services/answer (decides what may be served) and jobs/eval (re-checks every returned
answer independently, without trusting the service's verdict).

The answer is split into sentences (at . ! ? followed by whitespace, and at newlines). Per sentence:
  a. every [S#] names a provided source. Over the whole answer, an answer that must cite has >= 1.
  b. every number must equal a field of a source cited IN THAT SENTENCE, by role: a number directly
     followed by "allotment(s)" must equal that source's allotments; any other number must equal its
     closing_rank. A number in a sentence with no citation fails.
     Numbers are taken from the unmasked text, including ones glued to "." or "," (".999", ",57",
     "1,999"). Normalised: 1,234 = 1234; Indian grouping 1,00,011 = 100011; 2345.5 is exact.
     Masked (not checked): [S#] ids; "Round N" / "Rounds N and M" / "RN" with N in 1..3; and 2025 in
     a year context ("NEET-UG 2025", "in|of|for 2025", "2025 MCC|counselling|round|..."). A mask
     never applies when the digit is followed by [.,]digit or another digit ("Round 1,999" is a
     number). Every other number is checked (strict): user ranks, percentages, pages, pincodes.
  c. any "Round N" named in a sentence that cites sources must be the round of one of them.
  d. a closing-rank claim ("closing rank / closing AIR / cut-off / cutoff / last allotted rank|AIR /
     closed ... is|was|of|at|: X") must equal the closing_rank of a source cited in the sentence.
  e. rule g: a sentence that states a cited source's closing rank also names its round and its
     allotment count.
  f. the one code-generated exception: a sentence of the exact form
     "Your AIR X is at or below|above the Round N closing rank C [S#] for this cell." passes only if
     X equals the user's AIR extracted from the question, N and C match S#, and the relation is
     arithmetically right (X <= C -> "at or below"). The model's own text never gets this pass.
  h. a sentence that states any number must cite exactly one source (fail closed against swaps).
  g. any other sentence that compares "your rank / your AIR" (higher, lower, above, below, within ...)
     fails: rank comparisons are computed in code only.
Whole answer: no guarantee language; no line (20+ chars) of the system prompt (neet_common.leak).

Known limits: number words ("fifty-seven") are not detected; "17,95" is read as 1795.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel

from neet_common.leak import leaked_lines
from neet_common.schemas import Source

_NUM = r"(?:\.?\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|\.?\d+(?:\.\d+)?)"
_NUMBER = re.compile(rf"(?<![\d\w])((?:[-\u2212](?=[.\d]))?{_NUM})|(?<=[A-Za-z])({_NUM})")
_CITE = re.compile(r"\[\s*(S\d+(?:\s*[,;]\s*S\d+)*)\s*\]")
_SID = re.compile(r"S\d+")
_END = r"(?![.,]?\d)"
_MASKS = [
    _CITE,
    re.compile(rf"\bRound\s*[1-3]{_END}", re.IGNORECASE),
    re.compile(rf"\bRounds\s*[1-3]{_END}(?:\s*(?:,|and|&|or|to|-|\u2013)\s*[1-3]{_END})+", re.IGNORECASE),
    re.compile(rf"\bR[1-3]{_END}\b"),
    re.compile(
        rf"(?:NEET[\s-]*UG\s*|\b(?:in|of|for|year)\s+)2025{_END}"
        rf"|(?<![\d.,])2025{_END}(?=\s+(?:MCC|NEET|counsell?ing|AIQ|rounds?|data|allotments?)\b)",
        re.IGNORECASE,
    ),
]
_ROUND_DIGIT_MASKS = _MASKS[1:4]
_ALLOT_AFTER = re.compile(r"\s*allotments?\b", re.IGNORECASE)
_CLAIM = re.compile(
    r"(?:closing\s+(?:rank|AIR)|cut[\s-]?off|last\s+(?:allotted\s+|admitted\s+)?(?:rank|AIR)|\bclosed)"
    rf"[^\d\n]{{0,150}}?\b(?:is|was|were|of|at|=|:)\s*(?:an?\s+)?(?:AIR\s*)?({_NUM})",
    re.IGNORECASE,
)
_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")
# A fragment ending like this is an abbreviation ("S.M.S.", "Univ.", "Dr."), not the end of a sentence.
_ABBREV_END = re.compile(
    r"(?:\b[A-Za-z]\.|\b(?:Dr|Mr|Mrs|Ms|St|Univ|Govt|Inst|Med|Edu|No|Pvt|Ltd|Hosp|Hospt|Coll|Res|Sci|Dept)\.)$"
)


_NEW_STATEMENT = re.compile(r"(?:In\s+)?(?:Rounds?\b|R[1-3]\b|\[|The\b|This\b|Your\b)")


def sentences(text: str) -> list[str]:
    """Split at . ! ? + whitespace and at newlines, re-joining splits made after an abbreviation."""
    out: list[str] = []
    for line in text.split("\n"):
        parts = re.split(r"(?<=[.!?])\s+", line)
        for part in parts:
            rejoin = out and out[-1] != "\n" and _ABBREV_END.search(out[-1])
            if rejoin and not _NEW_STATEMENT.match(part):
                out[-1] = out[-1] + " " + part
            else:
                out.append(part)
        out.append("\n")  # hard boundary
    return [s for s in out if s.strip()]


_COMPARE = re.compile(
    rf"^Your AIR ({_NUM}) is (at or below|above) the Round ([1-3]) closing rank ({_NUM}) \[(S\d+)\] for this"
    r" cell\.$"
)
_GUARANTEE = re.compile(
    r"\b(?:definitely|guaranteed|certainly|surely|assured)\b|\byou\s+will\s+(?:\w+\s+)?get\b"
    r"|\byou'll\s+get\b|\bsure\s+to\s+get\b|\b100\s*%\s*(?:sure|chance)",
    re.IGNORECASE,
)
# Rank comparisons are computed in code (rule f). Any other sentence about the user's rank that uses
# comparison wording is rejected: the model has got the direction wrong before.
_USER_COMPARE = re.compile(
    r"\byour\s+(?:rank|AIR)\b.*\b(?:higher|lower|better|worse|above|below|within|outside|less|more|"
    r"greater|smaller|exceeds?|beyond)\b|\b(?:higher|lower|better|worse|above|below|within|outside)\b.*"
    r"\byour\s+(?:rank|AIR)\b"
    r"|\byou(?:\s+are|'re|'d|\s+would|\s+should|\s+will|\s+can|\s+could|\s+may|\s+might)\b[^.]{0,40}?"
    r"\b(?:within|clear|above|below|qualify|eligible|get\s+in|make\s+it)\b",
    re.IGNORECASE,
)
_AIR_WORD = r"(?:NEET\s+)?(?:AIR|all[\s-]+india\s+rank|rank)"
_AIR_NUM = r"(\d{1,3}(?:,\d{2,3})+|\d+)(?!\d|[.,]\d)"
# First-person phrasing only; never a cut-off / closing claim ("cut-off AIR 500", "closing AIR 500").
_USER_AIR = re.compile(
    rf"\bmy\s+{_AIR_WORD}\s*(?:is|=|:|of)?\s*{_AIR_NUM}"
    rf"|\bI\s+(?:have|got|had|scored|secured|hold)\s+(?:an?\s+)?{_AIR_WORD}\s*(?:of|:|=)?\s*{_AIR_NUM}"
    rf"|\bwith\s+(?:an?\s+)?{_AIR_WORD}\s*(?:of|:|=)?\s*{_AIR_NUM}"
    rf"|\bI\s+am\b[^.?!]{{0,30}}?\bAIR\s*(?:of|:|=)?\s*{_AIR_NUM}",
    re.IGNORECASE,
)


class VerifierResult(BaseModel):
    ok: bool
    errors: list[str]
    cited: list[str]
    numbers: list[str]


def to_decimal(text: str) -> Decimal | None:
    try:
        return Decimal(text.replace(",", ""))
    except InvalidOperation:
        return None


def cited_ids(text: str) -> list[str]:
    out: list[str] = []
    for m in _CITE.finditer(text):
        for sid in _SID.findall(m.group(1)):
            if sid not in out:
                out.append(sid)
    return out


_RANK_BEFORE = re.compile(r"\b(?:AIR|ranks?|cut[\s-]?offs?|closing)\b(?:\W+\w+){0,3}\W*$", re.IGNORECASE)


def _mask_spans(text: str) -> list[tuple[int, int]]:
    spans = [m.span() for pat in _MASKS[:-1] for m in pat.finditer(text)]
    for m in _MASKS[-1].finditer(text):  # the year: "NEET-UG 2025" always; otherwise never when a rank
        explicit = m.group(0).upper().startswith("NEET")  # word is within 3 words before it
        if explicit or not _RANK_BEFORE.search(text[: m.start()]):
            spans.append(m.span())
    return spans


def numbers_in(text: str) -> list[tuple[str, int, int]]:
    """(number text, start, end) for every number outside the masked spans. An attached leading minus
    stays part of the number, so "-1234" never equals 1234."""
    spans = _mask_spans(text)
    out = []
    for m in _NUMBER.finditer(text):
        g = 1 if m.group(1) else 2
        a, b = m.start(g), m.end(g)
        if not any(x <= a and b <= y for x, y in spans):
            out.append((m.group(g), a, b))
    return out


def masked(text: str) -> str:
    out = list(text)
    for a, b in _mask_spans(text):
        for i in range(a, b):
            if out[i].isdigit():
                out[i] = "#"
    return "".join(out)


def rounds_named(text: str) -> set[int]:
    named: set[int] = set()
    for pat in _ROUND_DIGIT_MASKS:
        for m in pat.finditer(text):
            named.update(int(d) for d in re.findall(r"(?<!\d)[1-3](?!\d)", m.group(0)))
    return named


def closing_claims(text: str) -> list[Decimal]:
    """Values asserted as a closing rank / cut-off in `text` (round labels and years masked)."""
    out = []
    for m in _CLAIM.finditer(masked(text)):
        val = to_decimal(m.group(1))
        if val is not None:
            out.append(val)
    return out


def user_air_spans(question: str) -> list[tuple[Decimal, int, int]]:
    """Every first-person AIR in the question: (value, start, end) of the number."""
    out = []
    for m in _USER_AIR.finditer(question):
        i = next(i for i in range(1, (m.lastindex or 0) + 1) if m.group(i))
        val = to_decimal(m.group(i))
        if val is not None:
            out.append((val, m.start(i), m.end(i)))
    return out


def extract_user_air(question: str) -> Decimal | None:
    """The user's own AIR, from first-person phrasing only. Two different values -> None (no guess)."""
    values = {v for v, _, _ in user_air_spans(question)}
    return values.pop() if len(values) == 1 else None


def comparison_sentence(
    user_air_text: str, sid: str, round_: int, rank_text: str, air: Decimal, closing: Decimal
) -> str:
    rel = "at or below" if air <= closing else "above"
    return (
        f"Your AIR {user_air_text} is {rel} the Round {round_} closing rank {rank_text} [{sid}] for"
        + " this cell."
    )


def _check_comparison(m: re.Match[str], by_id: dict[str, Source], user_air: Decimal | None) -> list[str]:
    air, rel, rnd, closing, sid = (
        to_decimal(m.group(1)),
        m.group(2),
        int(m.group(3)),
        to_decimal(m.group(4)),
        m.group(5),
    )
    src = by_id.get(sid)
    if src is None:
        return [f"comparison cites unknown [{sid}]"]
    errs = []
    if user_air is None or air != user_air:
        errs.append("comparison sentence states an AIR that is not the user's AIR from the question")
    if rnd != src.cell.round or closing != src.cell.closing_rank:
        errs.append(f"comparison sentence does not match [{sid}]")
    elif air is not None and (rel == "at or below") != (air <= src.cell.closing_rank):
        errs.append("comparison sentence states the wrong relation")
    return errs


def _check_sentence(sentence: str, by_id: dict[str, Source], user_air: Decimal | None) -> list[str]:
    s = sentence.strip()
    if m := _COMPARE.match(s):
        return _check_comparison(m, by_id, user_air)
    errors = []
    if _USER_COMPARE.search(s):
        errors.append("the model may not compare the user's rank with a figure (code adds that sentence)")
    sids = cited_ids(s)
    errors += [f"citation [{x}] does not match any provided source" for x in sids if x not in by_id]
    srcs = [by_id[x] for x in sids if x in by_id]
    named = rounds_named(s)
    if len(sids) > 1 and numbers_in(s):  # fail closed: figures from two rows in one sentence can swap
        errors.append("a sentence that states a figure must cite exactly one source")
    if srcs:
        for r in sorted(named - {x.cell.round for x in srcs}):
            errors.append(f"Round {r} is named in a sentence whose cited sources are from other rounds")
    closing_stated: set[Decimal] = set()
    allot_stated: set[Decimal] = set()
    for raw, _, end in numbers_in(s):
        val = to_decimal(raw)
        if val is None or not srcs:
            errors.append(f"number {raw} has no cited source in its sentence")
            continue
        if _ALLOT_AFTER.match(s, end):
            allot_stated.add(val)
            if all(Decimal(x.cell.allotments) != val for x in srcs):
                errors.append(f"number {raw} is not the allotment count of a source cited in its sentence")
        else:
            closing_stated.add(val)
            if all(x.cell.closing_rank != val for x in srcs):
                errors.append(f"number {raw} is not the closing rank of a source cited in its sentence")
    for m in _CLAIM.finditer(masked(s)):
        val = to_decimal(m.group(1))
        if val is None or all(x.cell.closing_rank != val for x in srcs):
            errors.append(f"claimed closing rank {m.group(1)} is not the closing rank of a cited source")
    for x in srcs:
        if x.cell.closing_rank in closing_stated:
            if x.cell.round not in named:
                errors.append(f"[{x.sid}] closing rank is stated without naming Round {x.cell.round}")
            if Decimal(x.cell.allotments) not in allot_stated:
                errors.append(f"[{x.sid}] closing rank is stated without its allotment count")
    return errors


def verify(
    answer: str,
    sources: list[Source],
    *,
    prompt_text: str,
    require_citation: bool = True,
    user_air: Decimal | None = None,
) -> VerifierResult:
    by_id = {s.sid: s for s in sources}
    errors: list[str] = []
    cited = cited_ids(answer)
    if require_citation and not any(c in by_id for c in cited):
        errors.append("the answer cites no source")
    for sentence in sentences(answer):
        if sentence.strip():
            errors += _check_sentence(sentence, by_id, user_air)
    for m in _GUARANTEE.finditer(answer):
        errors.append(f"guarantee language is not allowed: {m.group(0)!r}")
    for line in leaked_lines(answer, prompt_text):
        errors.append(f"answer repeats a system-prompt line: {line[:40]!r}...")
    return VerifierResult(
        ok=not errors,
        errors=list(dict.fromkeys(errors)),
        cited=cited,
        numbers=[n for n, _, _ in numbers_in(answer)],
    )
