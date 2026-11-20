"""eval/golden/questions.yaml: structure (always) and every expected value re-derived by the
independent oracle (when the raw MCC PDFs are present; skipped otherwise, e.g. in CI)."""

from decimal import Decimal
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "eval" / "golden" / "questions.yaml"
QUESTIONS = yaml.safe_load(GOLDEN.read_text(encoding="utf-8"))["questions"]
BY_ID = {q["id"]: q for q in QUESTIONS}

CLOSING = [
    (q["id"], i, v)
    for q in QUESTIONS
    for i, v in enumerate(q["expected_values"])
    if v.get("oracle", {}).get("kind") == "closing_rank"
]
PREDICTOR = [q for q in QUESTIONS if "inputs" in q and "expected_option_count" in q]
CHECKS = [(q["id"], c) for q in QUESTIONS for c in q.get("oracle_checks", [])]


def test_structure_and_mix():
    assert len(QUESTIONS) == 18
    assert len(BY_ID) == 18
    counts = {}
    for q in QUESTIONS:
        counts[q["category"]] = counts.get(q["category"], 0) + 1
        assert q["expected_behavior"] in ("answer", "refuse", "flag")
        assert isinstance(q["expected_values"], list)
        assert isinstance(q["must_not_contain"], list)
        if q["expected_behavior"] == "refuse":
            assert q["expected_values"] == []
        for v in q["expected_values"]:
            assert {"value", "file", "page", "how_derived"} <= v.keys()
    assert counts == {"answerable": 6, "out_of_index": 3, "injection": 3, "unsafe_advice": 2, "predictor": 4}


def test_every_closing_rank_value_carries_its_allotment_count():
    # project rule g: a closing rank is never stated without its round and allotment count.
    for _, _, v in CLOSING:
        assert isinstance(v["allotments"], int) and v["allotments"] >= 1
        assert v["oracle"]["round"] in (1, 2, 3)


def test_must_not_contain_file_exists():
    files = [q["must_not_contain_file"] for q in QUESTIONS if "must_not_contain_file" in q]
    assert files == ["services/answer/prompts/system.txt"]
    assert (ROOT / files[0]).is_file()


@pytest.mark.parametrize(("qid", "idx", "v"), CLOSING, ids=[f"{q}[{i}]" for q, i, _ in CLOSING])
def test_closing_rank_values_rederived_by_oracle(parsed, oc, qid, idx, v):
    o = v["oracle"]
    cr = oc.closing_rank(
        parsed[o["round"]].allotments, o["quota"], o["institute"], o["course"], o["category"]
    )
    assert cr.row is not None, f"{qid}: oracle finds no allotment for {o}"
    assert cr.closing_rank == Decimal(str(v["value"]))
    assert cr.matches == v["allotments"]
    assert (cr.row.file, cr.row.page, cr.row.line) == (v["file"], v["page"], v["line"])


@pytest.mark.parametrize("q", PREDICTOR, ids=[q["id"] for q in PREDICTOR])
def test_predictor_sets_rederived_by_oracle(parsed, seat_entries, opr, op, q):
    i = q["inputs"]
    pred = opr.predict(
        parsed[i["round"]].allotments,
        seat_entries,
        rank=Decimal(i["rank"]),
        category=i["category"],
        pwd=i["pwd"],
        quota=i["quota"],
        course=i["course"],
        state=i["state"],
    )
    assert len(pred.options) == q["expected_option_count"]
    assert pred.institutes_in_scope == q["institutes_in_scope"]
    for v in q["expected_values"]:
        if v.get("oracle", {}).get("kind") == "max_closing":
            m = pred.max_closing
            assert (m.closing_rank, m.allotments, m.page, m.line) == (
                Decimal(str(v["value"])),
                v["allotments"],
                v["page"],
                v["line"],
            )
            continue
        hits = [o for o in pred.options if op.squash(v["institute_match"]) in op.squash(o.institute)]
        assert len(hits) == 1, f"{q['id']}: {v['institute_match']!r} matches {len(hits)} options"
        got = [
            {
                "category": c.category,
                "closing_rank": c.rank_text,
                "allotments": c.allotments,
                "page": c.page,
                "line": c.line,
            }
            for c in hits[0].qualifying
        ]
        assert sorted(got, key=lambda c: c["category"]) == sorted(v["cells"], key=lambda c: c["category"])
        assert hits[0].state == v["state"]


@pytest.mark.parametrize(("qid", "check"), CHECKS, ids=[f"{q}:{c['kind']}" for q, c in CHECKS])
def test_refusal_preconditions_hold_in_the_data(parsed, oc, op, qid, check):
    if check["kind"] == "no_cell":
        cr = oc.closing_rank(
            parsed[check["round"]].allotments,
            check["quota"],
            check["institute"],
            check["course"],
            check["category"],
        )
        assert cr.closing_rank is None
    elif check["kind"] == "institute_absent":
        pat = op.squash(check["pattern"])
        for r in check["rounds"]:
            assert not [a for a in parsed[r].allotments if pat in op.squash(a.institute)]
    else:
        pytest.fail(f"{qid}: unknown oracle check {check['kind']}")
