"""Pydantic models that cross the retrieval <-> answer <-> eval HTTP boundaries."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------- retrieval


class ResolveRequest(BaseModel):
    text: str = Field(min_length=1, max_length=300)
    # Tokens the caller wants excluded (e.g. "the Manipal campus, not Mangalore" -> ["mangalore"]).
    exclude: list[str] = Field(default_factory=list, max_length=10)


class InstituteCandidate(BaseModel):
    id: int
    display_name: str
    short_name: str
    state: str | None
    fused_score: float
    ranks: dict[str, int | None]  # per-signal rank (1-based) or None when absent from that signal
    name_coverage: float  # idf-weighted share of query tokens found in the institute's name part
    full_coverage: float  # same, over the whole display string (name + address)


class ResolveResponse(BaseModel):
    status: Literal["resolved", "ambiguous", "not_found"]
    ambiguous: bool
    resolved_id: int | None
    candidates: list[InstituteCandidate]
    signals_used: list[str]


class InstituteNames(BaseModel):
    """Institute own names (first comma part of each display string), for scope exemptions."""

    names: list[str]


class CellsRequest(BaseModel):
    institute_id: int
    round: int | None = Field(default=None, ge=1, le=3)
    quota: str | None = None
    course: str | None = None
    allotted_category: str | None = None
    include_cw_nri: bool = True


class Cell(BaseModel):
    id: str  # stable source id, e.g. "cr:1:615:Open Seat Quota:MBBS:Open" (+ ":cwnri")
    round: int
    quota: str
    institute_id: int
    institute: str  # short name (no address, no digits from the address)
    state: str | None
    course: str
    allotted_category: str
    closing_rank: Decimal
    rank_text: str
    allotments: int
    is_cw_nri: bool
    file: str
    source_sha256: str
    page: int
    line: int


class CellsResponse(BaseModel):
    cells: list[Cell]
    truncated: bool


class SearchRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    k: int = Field(default=5, ge=1, le=20)
    kind: Literal["cell", "note"] | None = None


class SearchHit(BaseModel):
    chunk_id: int
    kind: str
    note: str | None
    text: str
    file: str
    page: int
    line: int | None
    fused_score: float
    ranks: dict[str, int | None]


class SearchResponse(BaseModel):
    hits: list[SearchHit]
    dropped_instruction_like: int
    signals_used: list[str]


# ---------------------------------------------------------------- answer


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    debug: bool = False  # true: include failed drafts and raw LLM slots in debug.trace (eval runner)


class Source(BaseModel):
    """One numbered source given to the model, built from exactly one Postgres row."""

    sid: str  # "S1", "S2", ...
    cell: Cell


class Citation(BaseModel):
    sid: str
    cell_id: str
    round: int
    quota: str
    institute: str
    course: str
    allotted_category: str
    closing_rank: Decimal
    rank_text: str
    allotments: int
    is_cw_nri: bool
    file: str
    source_sha256: str
    page: int
    line: int


class AskDebug(BaseModel):
    """What /ask returns about its own run. Unverified model drafts and raw LLM slots are kept out
    of it (they go to logs/answer.log) unless the request sets debug=true, which fills `trace`."""

    template: bool = False
    scope: str | None = None
    slots: dict[str, object] | None = None
    resolve: dict[str, object] | None = None
    verifier: dict[str, object] | None = None
    llm_calls: list[dict[str, float | int | None]] = Field(default_factory=list)
    error: str | None = None
    latency_s: float | None = None
    model: str | None = None
    trace: dict[str, object] | None = None


class AskResponse(BaseModel):
    answer: str
    status: Literal["answered", "refused", "clarify"]
    citations: list[Citation]
    sources: list[Source]
    debug: AskDebug
