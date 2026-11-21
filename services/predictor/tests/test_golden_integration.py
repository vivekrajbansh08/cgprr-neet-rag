"""POST /predict against the loaded database reproduces the locked predictor expectations (pred-* answer).

Expected sets and values are read at test time from the golden file named in eval/golden/LOCK.json;
no MCC figure is written in this file. Connects as neet_reader through the service lifespan. Skips
when the database is unreachable or empty.
"""

import json
import re
from collections.abc import Iterator
from typing import Any

import psycopg
import pytest
import yaml
from fastapi.testclient import TestClient
from neet_common.config import REPO_ROOT, Settings
from neet_common.db import connect
from neet_predictor.app import app

LOCK = REPO_ROOT / "eval" / "golden" / "LOCK.json"


def _questions() -> list[dict[str, Any]]:
    if not LOCK.exists():
        return []
    golden = REPO_ROOT / json.loads(LOCK.read_text(encoding="utf-8"))["file"]
    data = yaml.safe_load(golden.read_text(encoding="utf-8"))
    return [
        q
        for q in data["questions"]
        if q["category"] == "predictor" and q["expected_behavior"] == "answer" and "inputs" in q
    ]


PRED = _questions()


def squash(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    try:
        with connect(Settings(), "neet_reader", connect_timeout=3) as conn:
            if conn.execute("SELECT count(*) FROM neet.allotment").fetchone()[0] == 0:
                pytest.skip("neet.allotment is empty: run `make ingest`")
    except psycopg.Error as exc:
        pytest.skip(f"database not ready as neet_reader: {type(exc).__name__}")
    with TestClient(app) as c:
        yield c


@pytest.mark.parametrize("q", PRED, ids=[q["id"] for q in PRED])
def test_predict_matches_locked_golden(client: TestClient, q: dict[str, Any]) -> None:
    r = client.post("/predict", json=q["inputs"])
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["option_count"] == len(d["options"]) == q["expected_option_count"]
    assert d["institutes_in_scope"] == q["institutes_in_scope"]
    assert d["note"] and d["source_credit"].startswith("Source: Medical Counselling Committee")

    if q["expected_option_count"] == 0:
        assert d["options"] == []
        [ev] = q["expected_values"]
        b = d["best_in_scope"]
        assert b is not None
        assert (b["closing_rank"], b["allotments"], b["file"], b["page"], b["line"]) == (
            str(ev["value"]), ev["allotments"], ev["file"], ev["page"], ev["line"],
        )  # fmt: skip
        assert d["empty_message"] and b["closing_rank"] in d["empty_message"]
        return

    # Institute set: each expected match hits exactly one option, and every option is matched.
    matched: set[int] = set()
    for ev in q["expected_values"]:
        hits = [o for o in d["options"] if squash(ev["institute_match"]) in squash(o["institute"])]
        assert len(hits) == 1, f"{ev['institute_match']!r} matches {len(hits)} options"
        o = hits[0]
        matched.add(o["institute_id"])
        assert o["state"] == ev["state"]
        got = sorted(
            (c["category"], c["closing_rank"], c["allotments"], c["file"], c["page"], c["line"])
            for c in o["cells"]
        )
        want = sorted(
            (c["category"], str(c["closing_rank"]), c["allotments"], ev["file"], c["page"], c["line"])
            for c in ev["cells"]
        )
        assert got == want
        for c in o["cells"]:
            assert c["round"] == q["inputs"]["round"] and c["allotments"] >= 1
            assert c["closing_rank"] in o["explanation"] and f"Round {c['round']}" in o["explanation"]
    assert matched == {o["institute_id"] for o in d["options"]}
