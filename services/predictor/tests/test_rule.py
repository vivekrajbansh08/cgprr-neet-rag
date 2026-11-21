"""The predictor rule on small hand-checked synthetic rows (invented institutes and figures; no DB/LLM)."""

import re
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from neet_common.predictor import NOTE, SOURCE_CREDIT, PredictRequest
from neet_predictor.app import app, get_pool
from neet_predictor.rule import Row, eligible_categories, file_short, predict

SHA = "a" * 64


def row(iid, name, state, cat, rank, n, *, rnd=1, quota="Q1", course="MBBS", page=10, line=5, text=None):
    return Row(
        institute_id=iid, institute=name, state=state, round=rnd, quota=quota, course=course, category=cat,
        closing_rank=Decimal(str(rank)), rank_text=text or str(rank), allotments=n,
        file=f"r{rnd}_allotment_final.pdf", page=page, line=line, source_sha256=SHA,
    )  # fmt: skip


ROWS = [
    row(1, "Alpha College", "Northstate", "Open", 1200, 10, page=11, line=1),
    row(1, "Alpha College", "Northstate", "OBC", 1500, 4, page=12, line=2),
    row(2, "Beta College", "Northstate", "Open", 900, 7, page=13, line=3),
    row(2, "Beta College", "Northstate", "OBC", 1100, 1, page=14, line=4),
    row(2, "Beta College", "Northstate", "OBC PwD", 5000, 1, page=15, line=5),
    row(3, "Gamma College", "Southstate", "SC", 4000, 2, page=16, line=6),
    row(3, "Gamma College", "Southstate", "Open", 1000.5, 3, page=17, line=7, text="1000.5"),
    row(4, "Delta College", None, "Open", 2500, 9, page=18, line=8),
    # other round / quota / course: never used for a round-1, Q1, MBBS query
    row(5, "Epsilon College", "Northstate", "Open", 9999, 5, rnd=2),
    row(5, "Epsilon College", "Northstate", "Open", 9999, 5, quota="Q2"),
    row(5, "Epsilon College", "Northstate", "Open", 9999, 5, course="BDS"),
]


def req(**kw):
    base = {"rank": 1000, "category": "General", "pwd": False, "quota": "Q1", "course": "MBBS", "round": 1}
    return PredictRequest(**{**base, **kw})


def names(resp):
    return [o.institute for o in resp.options]


def test_eligible_categories():
    assert eligible_categories("General", False) == ["Open"]
    assert eligible_categories("OBC", False) == ["Open", "OBC"]
    assert eligible_categories("SC", True) == ["Open", "SC", "Open PwD", "SC PwD"]
    assert eligible_categories("General", True) == ["Open", "Open PwD"]


def test_general_uses_open_only():
    r = predict(ROWS, req(rank=1100))
    # Open >= 1100: Alpha 1200, Delta 2500. Beta Open 900 and Gamma Open 1000.5 fail; OBC/SC ignored.
    assert names(r) == ["Alpha College", "Delta College"]
    assert r.institutes_in_scope == 4  # Alpha, Beta, Gamma, Delta have Open round-1 Q1 MBBS cells
    assert r.eligible_categories == ["Open"]


def test_obc_adds_obc_cells():
    r = predict(ROWS, req(rank=1100, category="OBC"))
    # Beta qualifies on OBC 1100 (== AIR counts); Alpha on Open 1200 and OBC 1500.
    assert names(r) == ["Beta College", "Alpha College", "Delta College"]
    beta, alpha = r.options[0], r.options[1]
    assert [c.category for c in beta.cells] == ["OBC"]  # OBC PwD is not eligible without pwd
    assert [c.category for c in alpha.cells] == ["OBC", "Open"]  # sorted by category
    assert alpha.best_closing_rank == "1200"


def test_pwd_variants_are_eligible_only_with_pwd():
    assert "Beta College" not in names(predict(ROWS, req(rank=3000, category="OBC")))
    r = predict(ROWS, req(rank=3000, category="OBC", pwd=True))
    assert names(r) == ["Beta College"]
    assert [(c.category, c.closing_rank, c.allotments) for c in r.options[0].cells] == [
        ("OBC PwD", "5000", 1)
    ]


def test_no_round_k_allotment_never_qualifies():
    # Epsilon has rows only in round 2, quota Q2 or BDS: never in scope for this query.
    r = predict(ROWS, req(rank=1))
    assert "Epsilon College" not in names(r)
    assert r.institutes_in_scope == 4
    r2 = predict(ROWS, req(rank=1, round=2))
    assert names(r2) == ["Epsilon College"] and r2.options[0].cells[0].round == 2


def test_state_filter_and_unplaced_count():
    r = predict(ROWS, req(rank=900, state="Northstate"))
    assert names(r) == ["Beta College", "Alpha College"]
    assert r.institutes_in_scope == 2
    assert r.unplaced_no_state == 1  # Delta has no seat-matrix state; never guessed into Northstate
    assert all(o.state == "Northstate" for o in r.options)
    assert predict(ROWS, req(rank=900)).unplaced_no_state == 0  # no filter -> 0


def test_empty_result_reports_best_in_scope():
    r = predict(ROWS, req(rank=3000, state="Southstate"))
    assert r.options == [] and r.option_count == 0
    assert r.institutes_in_scope == 1
    b = r.best_in_scope
    assert b is not None
    assert (b.institute, b.category, b.round, b.closing_rank, b.allotments, b.page, b.line) == (
        "Gamma College", "Open", 1, "1000.5", 3, 17, 7,
    )  # fmt: skip
    assert r.empty_message is not None
    assert "1000.5 (Open, Round 1, 3 allotments) at Gamma College" in r.empty_message
    assert "AIR 3000" in r.empty_message and "Source r1 p17 l7." in r.empty_message


def test_nothing_in_scope():
    r = predict(ROWS, req(state="Nowhere"))
    assert r.options == [] and r.institutes_in_scope == 0 and r.best_in_scope is None
    assert r.empty_message is not None and "no closing rank" in r.empty_message


def test_best_in_scope_filled_when_options_exist():
    r = predict(ROWS, req(rank=1000))
    assert r.best_in_scope is not None and r.best_in_scope.closing_rank == "2500"
    assert r.empty_message is None


def test_sort_by_best_closing_rank_numeric_then_name():
    rows = [
        row(1, "Zeta", "S", "Open", 10000, 2),
        row(2, "Eta", "S", "Open", 9000, 2),
        row(3, "Alpha", "S", "Open", 10000, 2),
        row(4, "Theta", "S", "Open", 100000, 2),
    ]
    assert names(predict(rows, req(rank=1))) == ["Eta", "Alpha", "Zeta", "Theta"]


def test_explanation_numbers_equal_cell_fields():
    r = predict(ROWS, req(rank=1100, category="OBC"))
    alpha = r.options[1]
    assert alpha.explanation == (
        "OBC closing rank 1500 in Round 1 (4 allotments) is at or above your AIR 1100. Source r1 p12 l2. "
        "Open closing rank 1200 in Round 1 (10 allotments) is at or above your AIR 1100. Source r1 p11 l1."
    )
    assert "(1 allotment)" in r.options[0].explanation  # singular for one allotment
    for o in predict(ROWS, req(rank=7, category="SC", pwd=True)).options:
        allowed = {"7"}  # the user's AIR; every other number must be a cell field
        for c in o.cells:
            allowed |= {c.closing_rank, str(c.allotments), str(c.page), str(c.line), str(c.round)}
        assert set(re.findall(r"\d+(?:\.\d+)?", o.explanation)) <= allowed


def test_note_and_credit():
    r = predict(ROWS, req())
    assert r.note == NOTE and r.source_credit == SOURCE_CREDIT


def test_file_short():
    assert file_short("r1_allotment_final.pdf") == "r1"
    assert file_short("r3_something.pdf") == "r3"
    assert file_short("seat_matrix_x.pdf") == "seat_matrix_x"


@pytest.mark.parametrize(
    "body",
    [
        {"rank": 0, "category": "OBC", "quota": "Q", "course": "MBBS", "round": 1},
        {"rank": 10, "category": "Other", "quota": "Q", "course": "MBBS", "round": 1},
        {"rank": 10, "category": "OBC", "quota": "Q", "course": "MBBS", "round": 4},
        {"rank": 10, "category": "OBC", "quota": "Q", "course": "MBBS", "round": 0},
        {"rank": 10, "category": "OBC", "quota": "", "course": "MBBS", "round": 1},
    ],
)
def test_invalid_inputs_are_422(body):
    # No lifespan, no DB: a stand-in pool; validation must reject the body before any query runs.
    app.dependency_overrides[get_pool] = object
    try:
        assert TestClient(app).post("/predict", json=body).status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_blank_state_means_no_filter():
    assert req(state="  ").state is None
