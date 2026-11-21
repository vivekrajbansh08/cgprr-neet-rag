"""Institute-name token logic: tokenising, idf weights, coverage, and the ambiguity decision.

Pure code over data passed in (no DB, no globals), so it is unit-tested with invented names.

Why a token check on top of RRF: fused rank scores of near-identical names (two campuses of one
college) are close by construction, and so are those of unrelated institutes that share generic
words. Token coverage says which candidates actually contain what the user typed; the rarer a token
(idf), the more it counts. A query naming a word found in only one candidate's name wins.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from difflib import SequenceMatcher
from typing import Literal

from pydantic import BaseModel

# Words that carry no identity in a query for an institute name.
STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "of",
        "and",
        "at",
        "in",
        "for",
        "on",
        "to",
        "campus",
        "mbbs",
        "bds",
        "quota",
        "round",
        "closing",
        "rank",
        "cutoff",
        "cut",
        "off",
        "neet",
        "ug",
        "aiq",
        "seat",
        "seats",
        "category",
    }
)
# A candidate is "found" only if this share (idf-weighted) of the query tokens occur in its full
# display string. Generic words (medical, college) weigh little, so a query whose distinctive words
# match nothing (an institute absent from the data) falls below it.
MIN_FOUND_COVERAGE = 0.75
# Two top candidates whose three coverages all tie (within COVERAGE_TIE) are ambiguous, always:
# nothing the user typed tells them apart, and the fused RRF score (driven by how many chunks each
# institute has) must not break the tie.
COVERAGE_TIE = 1e-6
FUZZY_MIN = 0.85  # token similarity for spelling variants (Deoghar / Deogarh); tokens of 5+ chars
_TOKEN = re.compile(r"[a-z0-9]+")
# Long forms users type for names the MCC files print as abbreviations.
ALIASES = {
    "all india institute of medical sciences": "aiims",
    "jawaharlal institute of postgraduate medical education and research": "jipmer",
    "employees state insurance corporation": "esic",
}


# Generic abbreviations MCC prints inside names, normalised on both sides (query and catalog), so
# "Govt." = "Government", "Dental Sce." = "Dental Sciences". Word-level only; no institute names.
ABBREVIATIONS = {
    "govt": "government",
    "gov": "government",
    "sce": "sciences",
    "sci": "sciences",
    "science": "sciences",
    "med": "medical",
    "coll": "college",
    "inst": "institute",
    "univ": "university",
    "hosp": "hospital",
    "hospt": "hospital",
    "res": "research",
    "edu": "education",
}


def expand_aliases(query: str) -> str:
    q = re.sub(r"\s+", " ", query.lower())
    for long, short in ALIASES.items():
        q = q.replace(long, short)
    return q


def tokens(text: str) -> list[str]:
    out = [ABBREVIATIONS.get(t, t) for t in _TOKEN.findall(text.lower())]
    return [t for t in out if t not in STOPWORDS and not t.isdigit()]


def short_name(display_name: str, max_parts: int = 3) -> str:
    """Institute name without the address: comma parts up to the first one holding a digit, or the
    first one that restarts with the institute's first word (an address line restating the name)."""
    parts: list[str] = []
    for part in display_name.split(","):
        p = part.strip()
        if not p or any(ch.isdigit() for ch in p) or len(parts) == max_parts:
            break
        if parts and p.split()[0].lower() == parts[0].split()[0].lower():
            break
        parts.append(p)
    return ", ".join(parts) if parts else re.sub(r"\d", "", display_name).strip()


def head(display_name: str) -> str:
    """The first comma part: the institute's own name, without campus city or address."""
    return display_name.split(",", 1)[0]


# MCC prints "<name>,<address>": the name's own commas are followed by a space ("AIIMS, Jodhpur"),
# the join to the address is not (",BASNI ...") or has a space before it ("AIIMS Bathinda ,Jodhpur").
_NAME_JOIN = re.compile(r"\s+,|,(?=\S)")


_ADDRESS_WORDS = frozenset(
    {
        "road", "rd", "lane", "nagar", "street", "st", "po", "post", "near", "opp", "district", "dist",
        "pin", "campus", "sector", "plot", "block", "floor", "office", "dean", "principal", "the",
        "admission", "cell", "phase", "marg", "salai", "village", "via", "taluk", "tehsil",
    }
)  # fmt: skip


def _city_like(part: str, name: str) -> bool:
    """A short comma part right after a one-part name is its campus city ("GOVT. MEDICAL COLLEGE,
    AURANGABAD"), unless it restates the name or reads like an address line."""
    words = re.findall(r"[a-z]+", part.lower())
    first = re.findall(r"[a-z]+", name.lower())[:1]
    return (
        0 < len(words) <= 3
        and not any(ch.isdigit() for ch in part)
        and words[:1] != first
        and not any(w in _ADDRESS_WORDS for w in words)
    )


def name_part(display_name: str) -> str:
    """The institute's name with its campus city, without the address ("AIIMS, Jodhpur")."""
    m = _NAME_JOIN.search(display_name)
    if not m:
        return short_name(display_name).strip()
    name = display_name[: m.start()].strip()
    if "," not in name:  # MCC sometimes joins name and city with a tight comma too
        nxt = display_name[m.end() :].split(",", 1)[0].strip()
        if _city_like(nxt, name):
            name = f"{name}, {nxt}"
    return name


def name_parts(display_name: str) -> list[str]:
    return [p.strip() for p in name_part(display_name).split(",") if p.strip()]


def core_name(display_name: str) -> str:
    """Head plus the last comma part of the name: the campus city when the head is generic
    ("Kasturba Medical College, Manipal Univ., Mangalore" -> "Kasturba Medical College Mangalore")."""
    parts = name_parts(display_name)
    return " ".join(parts[:1] + parts[-1:]) if len(parts) > 1 else (parts[0] if parts else "")


class IdfIndex(BaseModel):
    """Document frequency of tokens over institute display names."""

    n_docs: int
    df: dict[str, int]

    @classmethod
    def build(cls, display_names: Iterable[str]) -> IdfIndex:
        df: dict[str, int] = {}
        n = 0
        for name in display_names:
            n += 1
            for t in set(tokens(name)):
                df[t] = df.get(t, 0) + 1
        return cls(n_docs=n, df=df)

    def idf(self, token: str) -> float:
        # Unknown tokens get the highest weight: a word no institute contains is very informative.
        return math.log((self.n_docs + 1) / (self.df.get(token, 0) + 0.5))


def _has(token: str, bag: set[str]) -> bool:
    if token in bag:
        return True
    if len(token) < 5:
        return False
    for b in bag:
        if len(b) < 5 or abs(len(b) - len(token)) > 2:  # ratio >= 0.85 needs near-equal lengths
            continue
        sm = SequenceMatcher(None, token, b)
        if sm.quick_ratio() >= FUZZY_MIN and sm.ratio() >= FUZZY_MIN:
            return True
    return False


def coverage(query: str, text: str, idf: IdfIndex) -> float:
    q = list(dict.fromkeys(tokens(query)))
    if not q:
        return 0.0
    bag = set(tokens(text))
    total = sum(idf.idf(t) for t in q)
    hit = sum(idf.idf(t) for t in q if _has(t, bag))
    return hit / total if total > 0 else 0.0


def core_coverage(query: str, display_name: str, idf: IdfIndex) -> float:
    """Coverage by the head and the campus city. A middle name part the user typed in full (every
    word of "Manipal Univ.") explains those words itself, so they are not read as the city: "Kasturba
    Medical College Manipal Univ" names the university both campuses share, not the Manipal campus."""
    q = list(dict.fromkeys(tokens(query)))
    parts = name_parts(display_name)
    if not q or not parts:
        return 0.0
    qset = set(q)
    head_bag = set(tokens(parts[0]))
    city_bag = set(tokens(parts[-1])) if len(parts) > 1 else set()
    middle: set[str] = set()
    for m in parts[1:-1]:
        mt = set(tokens(m))
        if mt and mt <= qset:
            middle |= mt
    total = sum(idf.idf(t) for t in q)
    hit = sum(idf.idf(t) for t in q if t in middle or _has(t, head_bag) or _has(t, city_bag))
    return hit / total if total > 0 else 0.0


def excluded(display_name: str, exclude: Iterable[str]) -> bool:
    bag = set(tokens(short_name(display_name)))
    return any(t in bag for e in exclude for t in tokens(e))


class Scored(BaseModel):
    id: int
    fused: float
    name_cov: float  # coverage over name_part(): the whole name with campus city, no address
    core_cov: float  # core_coverage(): head plus campus city
    head_cov: float  # coverage over head(): the first comma part
    full_cov: float  # coverage over the whole display string, address included
    head_in_query: bool = False  # every word of head() was typed: a generic head ("Govt Medical College")


def score(iid: int, fused: float, query: str, display_name: str, idf: IdfIndex) -> Scored:
    return Scored(
        id=iid,
        fused=fused,
        name_cov=coverage(query, name_part(display_name), idf),
        core_cov=core_coverage(query, display_name, idf),
        head_cov=coverage(query, head(display_name), idf),
        full_cov=coverage(query, display_name, idf),
        head_in_query=_head_in_query(query, display_name),
    )


def _head_in_query(query: str, display_name: str) -> bool:
    h = set(tokens(head(display_name)))
    return bool(h) and h <= set(tokens(query))


Decision = Literal["resolved", "ambiguous", "not_found"]


def key(s: Scored) -> tuple[float, float, float]:
    """Name-only ranking key: address text never decides a winner."""
    return (round(s.name_cov, 6), round(s.core_cov, 6), round(s.head_cov, 6))


def _tie(a: tuple[float, ...], b: tuple[float, ...]) -> bool:
    return all(abs(x - y) < COVERAGE_TIE for x, y in zip(a, b, strict=True))


def order_and_decide(items: list[Scored]) -> tuple[list[Scored], Decision]:
    """Sort candidates and decide 'resolved' | 'ambiguous' | 'not_found'. Fails closed.

    Order: name-part, core-name (head + campus city), head coverage, then full coverage and fused RRF
    score. The best must reach MIN_FOUND_COVERAGE (full) to count as found. Another found candidate
    is a rival (and the result ambiguous) when
      - it ties the best on the name key, or
      - it ties on name-part and core-name and its own head is made only of words the user typed
        (a generic head such as "Government Medical College": the head key must not pick a winner), or
      - the best's name does not explain the whole query (the address did part of the work) and the
        rival covers at least as much of the query in its full string.
    Address words can only send a question to clarify, never pick a winner. When ambiguous, the
    returned list is the best candidate plus its rivals.
    """
    ranked = sorted(items, key=lambda s: (*(-x for x in key(s)), -round(s.full_cov, 6), -s.fused, s.id))
    found = [s for s in ranked if s.full_cov >= MIN_FOUND_COVERAGE]
    if not found:
        return ranked, "not_found"
    top = found[0]
    name_explains_all = top.name_cov >= 1 - COVERAGE_TIE
    rivals = [
        s
        for s in found[1:]
        if _tie(key(s), key(top))
        or (_tie(key(s)[:2], key(top)[:2]) and s.head_in_query)
        or (not name_explains_all and s.full_cov >= top.full_cov - COVERAGE_TIE)
    ]
    if rivals:
        return [top, *rivals], "ambiguous"
    return found, "resolved"
