"""Integration: /ask through TestClient against the real DB (neet_reader) and the local LLM.

Skips cleanly when Postgres or the LLM endpoint is unreachable (CI has neither). Retrieval runs
in-process: its TestClient is an httpx.Client, so the answer pipeline still talks HTTP to it. No
real figures are hard-coded here; answers are checked against the rows they cite.
"""

from collections.abc import Iterator

import httpx
import psycopg
import pytest
from fastapi.testclient import TestClient
from neet_answer.app import SYSTEM_PROMPT
from neet_answer.pipeline import Pipeline
from neet_answer.retrieval_client import HttpRetrieval
from neet_common.config import Settings
from neet_common.db import connect
from neet_common.llm import LLMClient
from neet_common.verify import verify
from neet_retrieval.app import app as retrieval_app


@pytest.fixture(scope="module")
def settings() -> Settings:
    """Settings once the database is reachable as neet_reader (DB-only tests need nothing else)."""
    s = Settings()
    try:
        connect(s, "neet_reader", connect_timeout=3).close()
    except psycopg.OperationalError as exc:
        pytest.skip(f"database not reachable as neet_reader: {type(exc).__name__}")
    return s


@pytest.fixture(scope="module")
def llm_settings(settings: Settings) -> Settings:
    """Settings once the local LLM endpoint is also reachable."""
    try:
        httpx.get(settings.llm_base_url.rstrip("/") + "/models", timeout=3).raise_for_status()
    except httpx.HTTPError as exc:
        pytest.skip(f"LLM endpoint not reachable: {type(exc).__name__}")
    if not settings.llm_model:
        pytest.skip("LLM_MODEL not set")
    return settings


@pytest.fixture(scope="module")
def retrieval(settings: Settings) -> Iterator[TestClient]:
    with TestClient(retrieval_app, base_url="http://retrieval") as client:
        yield client


@pytest.fixture(scope="module")
def pipeline(llm_settings: Settings, retrieval: TestClient) -> Iterator[Pipeline]:
    with httpx.Client(timeout=llm_settings.llm_timeout_s) as http:
        yield Pipeline(
            LLMClient(llm_settings, http),
            HttpRetrieval("http://retrieval", retrieval),
            SYSTEM_PROMPT.read_text(encoding="utf-8"),
        )


def test_retrieval_cells_and_search(retrieval: TestClient):
    r = retrieval.post("/resolve_institute", json={"text": "Madras Medical College"}).json()
    assert r["status"] == "resolved"
    cells = retrieval.post("/cells", json={"institute_id": r["resolved_id"], "course": "MBBS"}).json()[
        "cells"
    ]
    assert cells and all(c["course"] == "MBBS" for c in cells)
    assert all(len(c["source_sha256"]) == 64 for c in cells)
    hits = retrieval.post("/search", json={"text": "quota abbreviation legend", "k": 3}).json()["hits"]
    assert hits


def test_resolver_flags_shared_names(retrieval: TestClient):
    for text in ("Kasturba Manipal", "JIPMER"):
        assert retrieval.post("/resolve_institute", json={"text": text}).json()["status"] == "ambiguous"
    for text in ("AIIMS New Delhi", "ESIC Medical College Gulbarga"):
        assert retrieval.post("/resolve_institute", json={"text": text}).json()["status"] == "resolved"


def test_lookup_answer_cites_the_rows_it_states(pipeline: Pipeline):
    q = (
        "What was the Round 2 closing rank for BDS at Maulana Azad Institute of Dental Sciences,"
        " All India quota, Open?"
    )
    r = pipeline.ask(q)
    assert r.status == "answered"
    assert r.citations
    assert verify(r.answer, r.sources, prompt_text=SYSTEM_PROMPT.read_text(encoding="utf-8")).ok
    assert all(c.round == 2 for c in r.citations)


def test_shared_name_asks_for_clarification(pipeline: Pipeline):
    r = pipeline.ask(
        "What was the Round 2 MBBS closing rank at Kasturba Medical College under the Deemed quota?"
    )
    assert r.status == "clarify"
    assert r.citations == []


def test_out_of_scope_year_is_refused(pipeline: Pipeline):
    assert pipeline.ask("What was the 2023 MBBS closing rank at Madras Medical College?").status == "refused"
