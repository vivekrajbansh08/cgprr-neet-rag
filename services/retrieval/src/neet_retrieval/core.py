"""Retrieval operations over a neet_reader connection pool: institute resolution, cells, hybrid search."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from neet_common.llm import LLMClient, LLMError
from neet_common.safety import looks_like_instruction
from neet_common.schemas import (
    Cell,
    CellsRequest,
    CellsResponse,
    InstituteCandidate,
    ResolveRequest,
    ResolveResponse,
    SearchHit,
    SearchRequest,
    SearchResponse,
)
from psycopg_pool import ConnectionPool
from pydantic import BaseModel

from neet_retrieval import sql
from neet_retrieval.fusion import rrf
from neet_retrieval.names import (
    IdfIndex,
    excluded,
    expand_aliases,
    order_and_decide,
    short_name,
    tokens,
)
from neet_retrieval.names import score as score_candidate

log = logging.getLogger("neet_retrieval")

SIGNAL_DEPTH = 20  # candidates taken from each signal before fusion
MAX_CANDIDATES = 5  # returned to the caller
MAX_CELLS = 200


class Institute(BaseModel):
    id: int
    display_name: str
    state: str | None


class Catalog(BaseModel):
    """Institute names and token statistics, loaded once per process in the lifespan."""

    institutes: dict[int, Institute]
    idf: IdfIndex


def load_catalog(pool: ConnectionPool) -> Catalog:
    with pool.connection() as conn:
        rows = conn.execute(sql.INSTITUTES).fetchall()
    inst = {r[0]: Institute(id=r[0], display_name=r[1], state=r[2]) for r in rows}
    return Catalog(institutes=inst, idf=IdfIndex.build(i.display_name for i in inst.values()))


def _vector_literal(v: Sequence[float]) -> str:
    return "[" + ",".join(f"{x:.7g}" for x in v) + "]"


def _embed(llm: LLMClient | None, text: str) -> str | None:
    if llm is None:
        return None
    try:
        return _vector_literal(llm.embed([text])[0])
    except LLMError as exc:
        log.warning("embedding unavailable, vector signal skipped: %s", exc)
        return None


def resolve_institute(
    pool: ConnectionPool, llm: LLMClient | None, cat: Catalog, req: ResolveRequest
) -> ResolveResponse:
    q = expand_aliases(req.text.strip())
    toks = tokens(q)
    rankings: dict[str, list[int]] = {}
    vec = _embed(llm, req.text)
    with pool.connection() as conn:
        rankings["trigram"] = [r[0] for r in conn.execute(sql.TRGM_INSTITUTES, {"q": q, "k": SIGNAL_DEPTH})]
        if toks:
            fts = [r[0] for r in conn.execute(sql.FTS_INSTITUTES, {"q": " ".join(toks), "k": SIGNAL_DEPTH})]
            if not fts:  # no institute has every word: fall back to any word
                fts = [
                    r[0]
                    for r in conn.execute(sql.FTS_INSTITUTES, {"q": " or ".join(toks), "k": SIGNAL_DEPTH})
                ]
            rankings["fts"] = fts
        if vec is not None:
            with conn.transaction():
                conn.execute(sql.SET_EF_SEARCH)
                rankings["vector"] = [
                    r[0] for r in conn.execute(sql.VEC_INSTITUTES, {"v": vec, "k": SIGNAL_DEPTH})
                ]
    fused, ranks = rrf(rankings)
    scored = []
    # Every catalog institute is scored (the catalog is small), so a rival that the search signals
    # missed can still make the decision fail closed. Fused RRF only orders exact coverage ties.
    for iid, inst in cat.institutes.items():
        if excluded(inst.display_name, req.exclude):
            continue
        scored.append(score_candidate(iid, fused.get(iid, 0.0), q, inst.display_name, cat.idf))
    ordered, status = order_and_decide(scored)  # ambiguous: only the candidates it cannot split
    candidates = [
        InstituteCandidate(
            id=s.id,
            display_name=cat.institutes[s.id].display_name,
            short_name=short_name(cat.institutes[s.id].display_name),
            state=cat.institutes[s.id].state,
            fused_score=round(s.fused, 6),
            ranks=ranks.get(s.id, dict.fromkeys(rankings)),
            name_coverage=round(s.name_cov, 4),
            full_coverage=round(s.full_cov, 4),
        )
        for s in ordered[:MAX_CANDIDATES]
    ]
    return ResolveResponse(
        status=status,
        ambiguous=status == "ambiguous",
        resolved_id=candidates[0].id if status == "resolved" else None,
        candidates=candidates,
        signals_used=list(rankings),
    )


def cell_id(round_: int, iid: int, quota: str, course: str, cat: str, cw_nri: bool) -> str:
    return f"cr:{round_}:{iid}:{quota}:{course}:{cat}" + (":cwnri" if cw_nri else "")


def get_cells(pool: ConnectionPool, req: CellsRequest) -> CellsResponse:
    params = {
        "iid": req.institute_id,
        "round": req.round,
        "quota": req.quota,
        "course": req.course,
        "cat": req.allotted_category,
        "cw": req.include_cw_nri,
        "lim": MAX_CELLS + 1,
    }
    with pool.connection() as conn:
        rows = conn.execute(sql.CELLS, params).fetchall()
    cells = [
        Cell(
            id=cell_id(r[0], r[2], r[1], r[3], r[4], r[13]),
            round=r[0],
            quota=r[1],
            institute_id=r[2],
            course=r[3],
            allotted_category=r[4],
            closing_rank=r[5],
            rank_text=r[6],
            allotments=r[7],
            file=r[8],
            source_sha256=r[14],
            page=r[9],
            line=r[10],
            institute=short_name(r[11]),
            state=r[12],
            is_cw_nri=r[13],
        )
        for r in rows[:MAX_CELLS]
    ]
    return CellsResponse(cells=cells, truncated=len(rows) > MAX_CELLS)


def search(pool: ConnectionPool, llm: LLMClient | None, req: SearchRequest) -> SearchResponse:
    depth = max(SIGNAL_DEPTH, 4 * req.k)
    rankings: dict[str, list[int]] = {}
    vec = _embed(llm, req.text)
    with pool.connection() as conn:
        rankings["fts"] = [
            r[0] for r in conn.execute(sql.FTS_CHUNKS, {"q": req.text, "kind": req.kind, "k": depth})
        ]
        if vec is not None:
            with conn.transaction():
                conn.execute(sql.SET_EF_SEARCH)
                rankings["vector"] = [
                    r[0] for r in conn.execute(sql.VEC_CHUNKS, {"v": vec, "kind": req.kind, "k": depth})
                ]
        fused, ranks = rrf(rankings)
        best = sorted(fused, key=lambda i: (-fused[i], i))
        rows = {r[0]: r for r in conn.execute(sql.CHUNKS_BY_ID, {"ids": best})}
    hits: list[SearchHit] = []
    dropped = 0
    for cid in best:
        r = rows[cid]
        if looks_like_instruction(r[3]):
            dropped += 1
            log.warning("dropped instruction-like chunk id=%s file=%s page=%s", cid, r[4], r[5])
            continue
        hits.append(
            SearchHit(
                chunk_id=cid,
                kind=r[1],
                note=r[2],
                text=r[3],
                file=r[4],
                page=r[5],
                line=r[6],
                fused_score=round(fused[cid], 6),
                ranks=ranks[cid],
            )
        )
        if len(hits) == req.k:
            break
    return SearchResponse(hits=hits, dropped_instruction_like=dropped, signals_used=list(rankings))
