"""Deterministic scope guard.

Indexed data: NEET-UG 2025 MCC All India Quota counselling, Rounds 1-3, MBBS / BDS / B.Sc. Nursing.

Two phases, both pure code:
- check_scope (before any LLM call): another year, an AYUSH/other UG course, a round other than 1-3.
- check_course_scope (after slot extraction, on the question with the grounded institute name
  removed): PG courses (MD, MS, DNB, NEET-PG ...). It runs later because PG-looking tokens occur
  inside institute names ("S.M.S. Medical College", "Post Graduate Institute of Dental Sciences",
  "Inst of PG Med Edu & Research"); the institute name is removed first so they never count.
"""

from __future__ import annotations

import re

from neet_common.verify import user_air_spans
from pydantic import BaseModel

DATA_YEAR = 2025
MAX_ROUND = 3

# A 19xx/20xx number is a year unless it is a rank/score ("AIR 2024", "rank of 2019", "score 2010")
# or part of a grouped number ("2,024", "2024,5").
_YEAR = re.compile(
    r"(?<![\d.,])(?<!AIR )(?<!rank )(?<!rank of )(?<!rank is )(?<!score )(?<!marks )"
    r"((?:19|20)\d{2})(?![.,]?\d)",
    re.IGNORECASE,
)
# Case-insensitive ("md general medicine"); dots on either side never count, so "S.M.S." and "Ms."
# are not courses.
_PG_ACRONYM = re.compile(r"(?<![\w.])(?:MD|MS|MDS|DM|MCh|M\.Ch\.?|DNB|M\.D\.|M\.S\.)(?![\w.])", re.IGNORECASE)
# PG intent: "PG" / "post graduate" / "postgraduation" anywhere, EXCEPT where the words are part of
# an institute name ("Post Graduate Institute of ...", "Inst of PG Med Edu", "Institute of
# Postgraduate Medical Education"). Catalog names are exempted separately in check_pg_scope.
_PG_PHRASE = re.compile(
    r"neet[\s-]*pg\b|super[\s-]*speciali"
    r"|\b(?:PG|post[\s-]*graduat\w*)\b(?!\s+(?:institute|inst\b|college|centre|center|school|med\b|"
    r"medical\s+(?:education|institute|college)|dental\s+(?:institute|college)))",
    re.IGNORECASE,
)
_OTHER_COURSE = re.compile(
    r"\b(?:BAMS|BHMS|BUMS|BSMS|BVSc|B\.?\s?V\.?Sc|B\.?\s?Pharm|BPT|AYUSH)\b", re.IGNORECASE
)
ROUND_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7}
_ORDINALS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6}
_ROUND_NUM = re.compile(
    r"\bround[\s-]*(\d+|one|two|three|four|five|six|seven)\b|\b(\d+)\s*(?:st|nd|rd|th)\s+round\b"
    r"|\b(first|second|third|fourth|fifth|sixth)\s+(?:counsell?ing\s+)?round\b|\bR(\d+)\b"
    r"|\b(\d+)\s*(?:st|nd|rd|th)\s+counsell?ing\s+round\b",
    re.IGNORECASE,
)
_ROUND_OTHER = re.compile(r"\bstray\b|\bmop[\s-]*up\b|\bspecial\s+round\b", re.IGNORECASE)
_PROMPT_NOUN = (
    r"(?:system\s+|hidden\s+|initial\s+|developer\s+|internal\s+|secret\s+|original\s+)?"
    r"(?:prompts?|instructions?|guidelines|rules|directives|configuration|context\s+window)"
)
_PROMPT_REQUEST = re.compile(
    r"\b(?:system|hidden|initial|developer|secret)\s+(?:prompt|instructions?|message)\b"
    r"|\byour\s+(?:prompt|instructions)\b"
    r"|\b(?:print|show|reveal|repeat|tell|give|output|display|dump|share|recite|list|copy|paste|"
    r"what\s+(?:are|is|were))\s+(?:me\s+)?(?:all\s+)?(?:of\s+)?(?:your|the\s+(?:system|hidden|initial))\s+"
    + _PROMPT_NOUN
    # "your guidelines for choosing a college" asks for advice, not for the assistant's prompt
    + r"\b(?!\s+(?:for|on|about|of|regarding|to|when|in)\b)",
    re.IGNORECASE,
)
PROMPT_REFUSAL = (
    "I can't share my instructions. I can answer questions about NEET-UG 2025 MCC counselling data,"
    " such as the closing rank for a course, institute, quota, category and round."
)
_GUARANTEE_ASK = re.compile(
    r"\b(?:surely|sure[\s-]*shot|definitely|definite|guarantee[ds]?|guaranteed|certainly|for\s+sure|"
    r"assured?)\b|\b100\s*%|\bwill\s+i\s+(?:\w+\s+){0,2}?get\b|\bam\s+i\s+(?:sure|certain)\b",
    re.IGNORECASE,
)
_EXCLUSION = re.compile(
    r"\b(?:not|excluding|except|other\s+than|rather\s+than)\s+(?:the\s+|at\s+|in\s+)?([A-Za-z][A-Za-z.\-]{2,})"
)
_EXCLUSION_NOISE = frozenset({"the", "any", "sure", "only", "get", "guaranteed", "allotted", "available"})


class ScopeResult(BaseModel):
    in_scope: bool
    reason: str | None = None  # machine-readable: year, pg_course, other_course, round
    message: str | None = None  # user-facing refusal text


def _refuse(reason: str, message: str) -> ScopeResult:
    return ScopeResult(in_scope=False, reason=reason, message=message)


def rounds_mentioned(question: str) -> list[int]:
    out = []
    for m in _ROUND_NUM.finditer(question):
        g = next(x for x in m.groups() if x).lower()
        out.append(int(g) if g.isdigit() else ROUND_WORDS.get(g) or _ORDINALS[g])
    return out


_RANKISH_BEFORE = re.compile(r"\b(?:AIR|rank|score|marks)\s*(?:is|of|:|=|-)?\s*$", re.IGNORECASE)


def years_mentioned(question: str) -> set[int]:
    """19xx/20xx numbers used as years. The user's own AIR (the same extractor the verifier uses) and
    any number right after AIR / rank / score / marks are not years."""
    air = [(a, b) for _, a, b in user_air_spans(question)]
    out = set()
    for m in _YEAR.finditer(question):
        a, b = m.span(1)
        if any(x <= a and b <= y for x, y in air) or _RANKISH_BEFORE.search(question[:a]):
            continue
        out.add(int(m.group(1)))
    return out


def check_scope(question: str) -> ScopeResult:
    years = sorted(years_mentioned(question) - {DATA_YEAR})
    if years:
        return _refuse(
            "year",
            f"The sources only cover NEET-UG {DATA_YEAR} MCC counselling. There is no data for"
            f" {', '.join(map(str, years))} in them, and I do not predict future cut-offs, so I cannot"
            " answer that.",
        )
    if _OTHER_COURSE.search(question):
        return _refuse(
            "other_course",
            "That course is not in the sources: they cover MCC counselling for MBBS, BDS and B.Sc."
            " Nursing only.",
        )
    if any(r < 1 or r > MAX_ROUND for r in rounds_mentioned(question)) or _ROUND_OTHER.search(question):
        return _refuse(
            "round",
            "That round is not in the sources: only the first three MCC rounds of"
            f" {DATA_YEAR} are indexed (no later, mop-up or stray-vacancy round).",
        )
    return ScopeResult(in_scope=True)


def _exempt_spans(question: str, catalog: list[str]) -> list[tuple[int, int]]:
    """Spans of the question that spell a catalog institute name (case/whitespace-insensitive)."""
    spans = []
    for name in catalog:
        words = name.split()
        if len(words) < 2:  # a one-word name ("GDC") is too weak to exempt anything
            continue
        pat = r"\s+".join(re.escape(w) for w in words)
        spans += [m.span() for m in re.finditer(pat, question, re.IGNORECASE)]
    return spans


def check_pg_scope(question: str, catalog: list[str]) -> ScopeResult:
    """PG-course check on the raw question, before any LLM call. A PG-looking token is exempt only
    inside a span that spells a catalog institute name; with no catalog it is refused (fail closed)."""
    spans = _exempt_spans(question, catalog)
    for pat in (_PG_ACRONYM, _PG_PHRASE):
        for m in pat.finditer(question):
            if not any(a <= m.start() and m.end() <= b for a, b in spans):
                return _refuse(
                    "pg_course",
                    "That is not in the sources: they cover NEET-UG counselling (MBBS, BDS, B.Sc. Nursing)"
                    " only, not postgraduate courses such as MD, MS or DNB.",
                )
    return ScopeResult(in_scope=True)


def strip_pg_tokens(text: str | None) -> str | None:
    """Remove PG course acronyms from an institute slot ("MD General Medicine at X" keeps X's words)."""
    if not text:
        return None
    out = re.sub(r"^.*?\b(?:MD|MS|DNB|MDS|MCh|DM)\b[^,]*?\bat\s+", "", text)
    out = _PG_ACRONYM.sub(" ", out)
    return re.sub(r"\s+", " ", out).strip(" ,") or None


def check_course_scope(question: str, institute_text: str | None) -> ScopeResult:
    """PG-course check on the question with the (question-grounded) institute name removed."""
    text = question.replace(institute_text, " ") if institute_text else question
    if _PG_ACRONYM.search(text) or _PG_PHRASE.search(text):
        return _refuse(
            "pg_course",
            "That is not in the sources: they cover NEET-UG counselling (MBBS, BDS, B.Sc. Nursing) only,"
            " not postgraduate courses such as MD, MS or DNB.",
        )
    return ScopeResult(in_scope=True)


def asks_for_prompt(question: str) -> bool:
    """The question asks the assistant to reveal its own instructions / system prompt. "What are the
    rules for upgradation" is about counselling rules, not a request for the assistant's prompt."""
    return _PROMPT_REQUEST.search(question) is not None


def asks_guarantee(question: str) -> bool:
    """The question wants a promise of an allotment ("Will I surely get ...", "guaranteed seat")."""
    return _GUARANTEE_ASK.search(question) is not None


def exclusion_terms(question: str, institute_text: str | None) -> list[str]:
    """Words the user explicitly excluded ("the Manipal campus, not Mangalore" -> ["mangalore"])."""
    named = set(re.findall(r"[a-z]+", (institute_text or "").lower()))
    out = []
    for m in _EXCLUSION.finditer(question):
        word = m.group(1).strip(".-").lower()
        if word not in _EXCLUSION_NOISE and word not in named:
            out.append(word)
    return out[:5]
