"""Pydantic models that cross the predictor <-> web / eval HTTP boundary (POST /predict, GET /form_options).

Field names are a contract with services/web and jobs/eval; do not rename them.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

CANDIDATE_CATEGORIES: tuple[str, ...] = ("General", "OBC", "EWS", "SC", "ST")
NOTE = "Based on 2025 data only; not a prediction or a guarantee."
SOURCE_CREDIT = "Source: Medical Counselling Committee (MCC), Government of India, mcc.nic.in"

CandidateCategory = Literal["General", "OBC", "EWS", "SC", "ST"]


class PredictRequest(BaseModel):
    rank: int = Field(gt=0, le=10_000_000, description="All India Rank (AIR)")
    category: CandidateCategory
    pwd: bool = False
    quota: str = Field(min_length=1, max_length=200)
    course: str = Field(min_length=1, max_length=100)
    round: int = Field(ge=1, le=3)
    state: str | None = Field(default=None, max_length=100)

    @field_validator("state")
    @classmethod
    def _blank_state_is_none(cls, v: str | None) -> str | None:
        return v if v and v.strip() else None


class PredictCell(BaseModel):
    round: int
    quota: str
    course: str
    category: str
    closing_rank: str  # rank_text exactly as printed by MCC
    allotments: int
    file: str
    page: int
    line: int
    source_sha256: str


class PredictOption(BaseModel):
    institute: str
    institute_id: int
    state: str | None
    best_closing_rank: str  # smallest qualifying closing rank (rank_text)
    cells: list[PredictCell]
    explanation: str


class BestInScope(BaseModel):
    institute: str
    category: str
    round: int
    closing_rank: str
    allotments: int
    file: str
    page: int
    line: int
    source_sha256: str


class PredictResponse(BaseModel):
    inputs: PredictRequest
    eligible_categories: list[str]
    options: list[PredictOption]
    option_count: int
    institutes_in_scope: int
    unplaced_no_state: int
    best_in_scope: BestInScope | None
    empty_message: str | None
    note: str = NOTE
    source_credit: str = SOURCE_CREDIT


class FormOptions(BaseModel):
    categories: list[str]
    quotas: list[str]
    courses: list[str]
    rounds: list[int]
    states: list[str]
