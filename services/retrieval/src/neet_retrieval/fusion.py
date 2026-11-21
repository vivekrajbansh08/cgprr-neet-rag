"""Reciprocal rank fusion (Cormack et al. 2009): score(d) = sum over signals of 1 / (k + rank_s(d))."""

from collections.abc import Hashable, Mapping, Sequence
from typing import TypeVar

RRF_K = 60
T = TypeVar("T", bound=Hashable)


def rrf(
    rankings: Mapping[str, Sequence[T]], k: int = RRF_K
) -> tuple[dict[T, float], dict[T, dict[str, int | None]]]:
    """Fuse ranked lists (best first). Returns (score per item, 1-based rank per signal per item)."""
    scores: dict[T, float] = {}
    ranks: dict[T, dict[str, int | None]] = {}
    for signal, items in rankings.items():
        for pos, item in enumerate(items, 1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + pos)
            ranks.setdefault(item, dict.fromkeys(rankings))[signal] = pos
    for item in ranks:
        for signal in rankings:
            ranks[item].setdefault(signal, None)
    return scores, ranks
