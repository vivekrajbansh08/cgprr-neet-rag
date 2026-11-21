"""Pure aggregation helpers for the bench job (no I/O, unit-tested with fakes).

Percentiles use linear interpolation between closest ranks (the same definition as numpy's default
`percentile(..., method="linear")` / Excel PERCENTILE.INC): position p/100 * (n - 1) in the sorted list.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Any

PERCENTILE_METHOD = "linear interpolation between closest ranks (numpy default / PERCENTILE.INC)"


def percentile(values: list[float], p: float) -> float | None:
    """The p-th percentile (0..100) of `values` by linear interpolation; None for an empty list."""
    if not values:
        return None
    if not 0 <= p <= 100:
        raise ValueError(f"percentile p must be in [0, 100], got {p}")
    xs = sorted(values)
    pos = p / 100 * (len(xs) - 1)
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return float(xs[lo])
    return float(xs[lo] + (xs[hi] - xs[lo]) * (pos - lo))


def llm_usage(resp: dict[str, Any]) -> tuple[float, int, int]:
    """(LLM seconds, completion tokens, LLM call count) from an /ask response's debug.llm_calls.

    Same accounting as jobs/eval: sum of `seconds` and `completion_tokens` over all calls; a missing
    value counts as 0.
    """
    calls = (resp.get("debug") or {}).get("llm_calls") or []
    seconds = sum(float(c.get("seconds") or 0.0) for c in calls)
    tokens = sum(int(c.get("completion_tokens") or 0) for c in calls)
    return seconds, tokens, len(calls)


def latency_summary(latencies: list[float]) -> dict[str, Any]:
    return {
        "n": len(latencies),
        "p50_s": percentile(latencies, 50),
        "p95_s": percentile(latencies, 95),
        "mean_s": sum(latencies) / len(latencies) if latencies else None,
        "min_s": min(latencies) if latencies else None,
        "max_s": max(latencies) if latencies else None,
    }


def ask_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate timed /ask records: {e2e_s, llm_s, completion_tokens, llm_calls, status, ok}.

    LLM time share = sum LLM s / sum e2e s; tokens/s = sum completion tokens / sum LLM s (aggregate,
    not a mean of per-request rates). Only successful requests (ok=True) feed the timing figures;
    failed ones are counted under their status.
    """
    ok = [r for r in records if r.get("ok")]
    e2e = [r["e2e_s"] for r in ok]
    sum_e2e = sum(e2e)
    sum_llm = sum(r["llm_s"] for r in ok)
    sum_tok = sum(r["completion_tokens"] for r in ok)
    out = latency_summary(e2e)
    out.update(
        {
            "requests": len(records),
            "errors": len(records) - len(ok),
            "status_counts": dict(sorted(Counter(r["status"] for r in records).items())),
            "sum_e2e_s": sum_e2e,
            "sum_llm_s": sum_llm,
            "llm_calls": sum(r["llm_calls"] for r in ok),
            "completion_tokens": sum_tok,
            "llm_time_share": sum_llm / sum_e2e if sum_e2e else None,
            "gen_tokens_per_s": sum_tok / sum_llm if sum_llm else None,
        }
    )
    return out


def cycle(items: list[Any], n: int) -> list[Any]:
    """The first n items of items repeated in order (items[0], items[1], ..., items[0], ...)."""
    if n <= 0:
        return []
    if not items:
        raise ValueError("cannot cycle an empty list")
    return [items[i % len(items)] for i in range(n)]
