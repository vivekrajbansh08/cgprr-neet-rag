"""The three timed phases: /ask, embeddings, /predict. HTTP clients are injected (tests use fakes).

Nothing returned here contains an MCC figure: /ask and /predict bodies are reduced to status,
timing and token counts; chunk texts are embedded but never stored or printed.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import httpx
from neet_common.config import Settings

from neet_bench.stats import ask_summary, cycle, latency_summary, llm_usage

# Fixed, parameterised: the first K chunk texts in id order (deterministic across runs).
CHUNK_SQL = "SELECT text FROM neet.chunk ORDER BY id LIMIT %s"

Clock = Callable[[], float]


def ask_once(
    client: httpx.Client, url: str, question: str, clock: Clock = time.perf_counter
) -> dict[str, Any]:
    t0 = clock()
    try:
        resp = client.post(url.rstrip("/") + "/ask", json={"question": question, "debug": True})
        resp.raise_for_status()
        body = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        return {"ok": False, "status": f"error:{type(exc).__name__}", "e2e_s": clock() - t0,
                "llm_s": 0.0, "completion_tokens": 0, "llm_calls": 0}  # fmt: skip
    e2e = clock() - t0
    llm_s, tokens, calls = llm_usage(body)
    return {"ok": True, "status": str(body.get("status")), "e2e_s": e2e, "llm_s": llm_s,
            "completion_tokens": tokens, "llm_calls": calls}  # fmt: skip


def run_ask(
    client: httpx.Client,
    url: str,
    questions: list[tuple[str, str]],
    n: int,
    warmup: int,
    clock: Clock = time.perf_counter,
    log: Callable[[str], None] = print,
) -> dict[str, Any]:
    """questions: (id, text). Warm-ups are the first `warmup` items of the cycle and are discarded."""
    plan = cycle(questions, warmup + n)
    records: list[dict[str, Any]] = []
    warm: list[dict[str, Any]] = []
    for i, (qid, text) in enumerate(plan):
        rec = ask_once(client, url, text, clock) | {"id": qid}
        (warm if i < warmup else records).append(rec)
        tag = "warmup" if i < warmup else f"{i - warmup + 1}/{n}"
        log(f"/ask {tag:>7} {qid:8} {rec['status']:10} {rec['e2e_s']:6.2f}s llm {rec['llm_s']:6.2f}s")
    return {
        "url": url,
        "warmup": warmup,
        "warmup_e2e_s": [r["e2e_s"] for r in warm],
        "question_ids": [q[0] for q in questions],
        "per_request": records,
        "summary": ask_summary(records),
    }


def run_predict(
    client: httpx.Client,
    url: str,
    inputs: list[tuple[str, dict[str, Any]]],
    n: int,
    warmup: int,
    clock: Clock = time.perf_counter,
) -> dict[str, Any]:
    plan = cycle(inputs, warmup + n)
    lat: list[float] = []
    errors = 0
    for i, (_qid, body) in enumerate(plan):
        t0 = clock()
        try:
            resp = client.post(url.rstrip("/") + "/predict", json=body)
            resp.raise_for_status()
            resp.json()
            ok = True
        except (httpx.HTTPError, ValueError):
            ok = False
        dt = clock() - t0
        if i >= warmup:
            if ok:
                lat.append(dt)
            else:
                errors += 1
    summary = latency_summary(lat) | {"requests": n, "errors": errors}
    return {"url": url, "warmup": warmup, "question_ids": [q[0] for q in inputs], "summary": summary}


def run_embed(
    client: httpx.Client,
    settings: Settings,
    texts: list[str],
    batch: int,
    embed: Callable[[httpx.Client, Settings, list[str], int], list[list[float]]],
    clock: Clock = time.perf_counter,
) -> dict[str, Any]:
    """One warm-up batch (untimed), then all `texts` in batches of `batch`, timed as a whole."""
    if not texts:
        return {"error": "no chunk texts (is neet.chunk empty? run `make index`)"}
    t0 = clock()
    embed(client, settings, texts[:batch], batch)
    warm_s = clock() - t0
    t1 = clock()
    vectors = embed(client, settings, texts, batch)
    dt = clock() - t1
    return {
        "model": settings.embed_model,
        "chunks": len(texts),
        "batch_size": batch,
        "batches": -(-len(texts) // batch),
        "dim": len(vectors[0]) if vectors else None,
        "warmup_batch_s": warm_s,
        "seconds": dt,
        "chunks_per_s": len(texts) / dt if dt else None,
    }
