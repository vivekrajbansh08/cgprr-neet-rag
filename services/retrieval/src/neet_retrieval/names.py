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


def expand_aliases(query: str) -> str:
    q = re.sub(r"\s+", " ", query.lower())
    for long, short in ALIASES.items():
        q = q.replace(long, short)
    return q


def tokens(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in STOPWORDS and not t.isdigit()]


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
    return any(len(b) >= 5 and SequenceMatcher(None, token, b).ratio() >= FUZZY_MIN for b in bag)


def coverage(query: str, text: str, idf: IdfIndex) -> float:
    q = list(dict.fromkeys(tokens(query)))
    if not q:
        return 0.0
    bag = set(tokens(text))
    total = sum(idf.idf(t) for t in q)
    hit = sum(idf.idf(t) for t in q if _has(t, bag))
    return hit / total if total > 0 else 0.0


def excluded(display_name: str, exclude: Iterable[str]) -> bool:
    bag = set(tokens(short_name(display_name)))
    return any(t in bag for e in exclude for t in tokens(e))


class Scored(BaseModel):
    id: int
    fused: float
    head_cov: float  # coverage over head(): the institute's own name
    name_cov: float  # coverage over short_name(): name plus campus city, no address
    full_cov: float  # coverage over the whole display string


Decision = Literal["resolved", "ambiguous", "not_found"]


def _key(s: Scored) -> tuple[float, float, float]:
    return (round(s.head_cov, 6), round(s.name_cov, 6), round(s.full_cov, 6))


def order_and_decide(items: list[Scored]) -> tuple[list[Scored], Decision]:
    """Sort candidates and decide 'resolved' | 'ambiguous' | 'not_found'.

    Order: head coverage, name coverage, full coverage (a word in the institute's own name beats the
    same word in its address), then fused RRF score. The best must reach MIN_FOUND_COVERAGE (full) to
    count as found. It is ambiguous whenever the runner-up ties on all three coverages.
    """
    ranked = sorted(items, key=lambda s: (*(-x for x in _key(s)), -s.fused, s.id))
    found = [s for s in ranked if s.full_cov >= MIN_FOUND_COVERAGE]
    if not found:
        return ranked, "not_found"
    top = found[0]
    if len(found) > 1:
        nxt = found[1]
        tie = all(abs(a - b) < COVERAGE_TIE for a, b in zip(_key(top), _key(nxt), strict=True))
        if tie:
            return found, "ambiguous"
    return found, "resolved"
