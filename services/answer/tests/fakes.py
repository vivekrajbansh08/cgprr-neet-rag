"""Fakes for answer-service unit tests: no network, no real LLM, invented values only."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from neet_common.llm import ChatResult
from neet_common.schemas import (
    Cell,
    CellsRequest,
    CellsResponse,
    InstituteCandidate,
    ResolveRequest,
    ResolveResponse,
    Source,
)


def cell(
    round_: int = 1,
    closing: str = "1234",
    allotments: int = 7,
    *,
    institute_id: int = 1,
    institute: str = "Alpha Medical College, Northtown",
    quota: str = "All India",
    course: str = "MBBS",
    category: str = "Open",
    cw_nri: bool = False,
) -> Cell:
    return Cell(
        id=f"cr:{round_}:{institute_id}:{quota}:{course}:{category}" + (":cwnri" if cw_nri else ""),
        round=round_,
        quota=quota,
        institute_id=institute_id,
        institute=institute,
        state="Somestate",
        course=course,
        allotted_category=category,
        closing_rank=Decimal(closing),
        rank_text=closing,
        allotments=allotments,
        is_cw_nri=cw_nri,
        file=f"r{round_}_allotment_final.pdf",
        source_sha256="0" * 64,
        page=10,
        line=20,
    )


def sources(*cells: Cell) -> list[Source]:
    return [Source(sid=f"S{i}", cell=c) for i, c in enumerate(cells, 1)]


def candidate(iid: int, name: str, score: float = 0.049) -> InstituteCandidate:
    return InstituteCandidate(
        id=iid,
        display_name=name + ", Somestate, 000000",
        short_name=name,
        state="Somestate",
        fused_score=score,
        ranks={"trigram": 1, "fts": 1, "vector": 1},
        name_coverage=1.0,
        full_coverage=1.0,
    )


class FakeLLM:
    """Returns scripted answers. The first call (slot extraction) returns `slots` as JSON."""

    def __init__(self, slots: dict[str, Any] | None = None, answers: list[str] | None = None) -> None:
        self.slots = slots
        self.answers = list(answers or [])
        self.calls: list[list[dict[str, str]]] = []

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        json_schema: dict[str, Any] | None = None,
        schema_name: str = "output",
        max_tokens: int = 600,
        seed: int = 7,
    ) -> ChatResult:
        self.calls.append(messages)
        if json_schema is not None:
            assert self.slots is not None, "slot extraction was not expected"
            return ChatResult(content=json.dumps(self.slots), completion_tokens=20, seconds=0.01)
        content = self.answers.pop(0) if self.answers else "No answer."
        return ChatResult(content=content, completion_tokens=30, seconds=0.01)


class FakeRetrieval:
    def __init__(
        self, resolve: ResolveResponse, cells: list[Cell] | None = None, names: list[str] | None = None
    ) -> None:
        self._names = names or []
        self._resolve = resolve
        self._cells = cells or []
        self.resolve_requests: list[ResolveRequest] = []
        self.cell_requests: list[CellsRequest] = []

    def resolve(self, req: ResolveRequest) -> ResolveResponse:
        self.resolve_requests.append(req)
        return self._resolve

    def institute_names(self) -> list[str]:
        return self._names

    def cells(self, req: CellsRequest) -> CellsResponse:
        self.cell_requests.append(req)
        out = [
            c
            for c in self._cells
            if (req.quota is None or c.quota == req.quota)
            and (req.course is None or c.course == req.course)
            and (req.allotted_category is None or c.allotted_category == req.allotted_category)
            and (req.include_cw_nri or not c.is_cw_nri)
        ]
        return CellsResponse(cells=out, truncated=False)


def resolved(cand: InstituteCandidate) -> ResolveResponse:
    return ResolveResponse(
        status="resolved", ambiguous=False, resolved_id=cand.id, candidates=[cand], signals_used=["trigram"]
    )


def ambiguous(*cands: InstituteCandidate) -> ResolveResponse:
    return ResolveResponse(
        status="ambiguous", ambiguous=True, resolved_id=None, candidates=list(cands), signals_used=["trigram"]
    )


def not_found() -> ResolveResponse:
    return ResolveResponse(
        status="not_found", ambiguous=False, resolved_id=None, candidates=[], signals_used=["trigram"]
    )
