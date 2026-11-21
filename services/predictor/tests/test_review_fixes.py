"""Reviewer findings: unknown quota/course/state are 422 (never a false "no institute"), CW/NRI rows
never reach /predict, best_in_scope ties go to PDF order. Invented data; the DB test skips without a DB."""

import re
from collections.abc import Iterator
from decimal import Decimal

import psycopg
import pytest
from fastapi.testclient import TestClient
from neet_common.config import Settings
from neet_common.db import connect
from neet_common.predictor import FormOptions, PredictRequest
from neet_predictor import sql
from neet_predictor.app import app, get_form_values, get_pool
from neet_predictor.rule import Row, predict

FORM = FormOptions(
    categories=["General", "OBC", "EWS", "SC", "ST"],
    quotas=["Q1", "Q2"],
    courses=["MBBS"],
    rounds=[1, 2, 3],
    states=["Northstate"],
)
BODY = {"rank": 100, "category": "OBC", "pwd": False, "quota": "Q1", "course": "MBBS", "round": 1}


@pytest.fixture
def offline(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    app.dependency_overrides[get_pool] = object
    app.dependency_overrides[get_form_values] = lambda: FORM
    monkeypatch.setattr(sql, "fetch_rows", lambda *a, **k: [])
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize(
    ("field", "value"),
    [("quota", "Bogus"), ("quota", "q1"), ("course", "MD"), ("state", "northstate"), ("state", "Nowhere")],
)
def test_unknown_quota_course_state_is_422(offline: TestClient, field: str, value: str) -> None:
    r = offline.post("/predict", json={**BODY, field: value})
    assert r.status_code == 422, r.text
    assert field in r.text


def test_known_values_pass_validation(offline: TestClient) -> None:
    assert offline.post("/predict", json={**BODY, "state": "Northstate"}).status_code == 200
    assert offline.post("/predict", json={**BODY, "state": None}).status_code == 200


def test_rows_sql_reads_only_closing_rank_view() -> None:
    tables = set(re.findall(r"\bneet\.(\w+)", sql.ROWS))
    assert tables == {"closing_rank", "institute", "source_file"}
    assert "closing_rank_cw_nri" not in sql.ROWS and "allotment " not in sql.ROWS


def _row(iid: str, name: str, cat: str, rank: int, file: str, page: int, line: int) -> Row:
    return Row(
        institute_id=int(iid), institute=name, state="S", round=1, quota="Q1", course="MBBS", category=cat,
        closing_rank=Decimal(rank), rank_text=str(rank), allotments=2, file=file, page=page, line=line,
        source_sha256="0" * 64,
    )  # fmt: skip


def test_best_in_scope_tie_goes_to_pdf_order() -> None:
    # Equal top closing rank 900: "Aardvark" sorts first by name, but "Zebra" comes first in the PDF.
    rows = [
        _row("1", "Aardvark College", "Open", 900, "r1_allotment_final.pdf", 20, 5),
        _row("2", "Zebra College", "OBC", 900, "r1_allotment_final.pdf", 12, 40),
        _row("3", "Mid College", "Open", 900, "r1_allotment_final.pdf", 12, 41),
        _row("4", "Low College", "Open", 500, "r1_allotment_final.pdf", 1, 1),
    ]
    req = PredictRequest(rank=1000, category="OBC", quota="Q1", course="MBBS", round=1)
    b = predict(rows, req).best_in_scope
    assert b is not None and (b.institute, b.page, b.line) == ("Zebra College", 12, 40)


# ------------------------------------------------------------------ DB: CW / NRI rows never reach /predict

CW_NRI_POSITIONS = """
SELECT DISTINCT a.round, a.quota, a.course, f.file_name, a.page, a.line
FROM neet.allotment a JOIN neet.source_file f ON f.id = a.source_file_id
WHERE a.is_cw_nri
"""


@pytest.fixture(scope="module")
def cw_nri() -> set[tuple]:
    try:
        with connect(Settings(), "neet_reader", connect_timeout=3) as conn:
            rows = {tuple(r) for r in conn.execute(CW_NRI_POSITIONS)}
    except psycopg.Error as exc:
        pytest.skip(f"database not ready as neet_reader: {type(exc).__name__}")
    if not rows:
        pytest.skip("no CW/NRI allotments loaded: run `make ingest`")
    return rows


@pytest.fixture(scope="module")
def live() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


def test_predict_never_returns_cw_or_nri_rows(cw_nri: set[tuple], live: TestClient) -> None:
    form = live.get("/form_options").json()
    positions = {(f, p, ln) for *_, f, p, ln in cw_nri}
    combos = sorted({(rnd, q, c) for rnd, q, c, *_ in cw_nri})
    checked_cw_only = checked_shared = 0
    for rnd, quota, course in combos:
        body = {"rank": 1, "category": "SC", "pwd": True, "quota": quota, "course": course, "round": rnd}
        if quota not in form["quotas"] or course not in form["courses"]:
            # A quota with only CW/NRI allotments has no neet.closing_rank row at all: nothing to predict.
            assert live.post("/predict", json=body).status_code == 422
            checked_cw_only += 1
            continue
        for cat in ("SC", "OBC", "EWS", "ST"):
            d = live.post("/predict", json={**body, "category": cat}).json()
            cells = [c for o in d["options"] for c in o["cells"]]
            assert not {(c["file"], c["page"], c["line"]) for c in cells} & positions
            b = d["best_in_scope"]
            assert b is None or (b["file"], b["page"], b["line"]) not in positions
        checked_shared += 1
    assert checked_cw_only + checked_shared == len(combos)
