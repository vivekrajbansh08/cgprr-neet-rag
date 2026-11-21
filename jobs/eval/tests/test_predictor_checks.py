"""Predictor scoring with invented questions and fake /predict responses (no real MCC figures, no network)."""

import copy

from neet_common.predictor import PredictResponse
from neet_eval.__main__ import score_table, uses_predictor
from neet_eval.predictor_checks import check_prediction

INPUTS = {
    "rank": 500, "category": "OBC", "pwd": False, "quota": "Q1", "course": "MBBS", "round": 1, "state": None,
}  # fmt: skip
Q = {
    "id": "p-01",
    "category": "predictor",
    "expected_behavior": "answer",
    "inputs": INPUTS,
    "expected_option_count": 2,
    "institutes_in_scope": 5,
    "expected_values": [
        {"value": "Alpha", "institute_match": "Alpha  Medical", "file": "r1.pdf", "page": 3,
         "cells": [{"category": "Open", "closing_rank": "600", "allotments": 4, "page": 3, "line": 9}]},
        {"value": "Beta", "institute_match": "BETA MEDICAL", "file": "r1.pdf", "page": 4,
         "cells": [{"category": "OBC", "closing_rank": "700", "allotments": 1, "page": 4, "line": 2}]},
    ],
    "must_not_contain": ["Gamma Medical", "guaranteed"],
}  # fmt: skip


def cell(cat, cr, n, page, line, rnd=1):
    return {"round": rnd, "quota": "Q1", "course": "MBBS", "category": cat, "closing_rank": cr,
            "allotments": n, "file": "r1.pdf", "page": page, "line": line,
            "source_sha256": "0" * 64}  # fmt: skip


def option(name, iid, cells):
    return {"institute": name, "institute_id": iid, "state": "S",
            "best_closing_rank": cells[0]["closing_rank"], "cells": cells, "explanation": "x"}  # fmt: skip


def response(options, scope=5, best=None, empty=None):
    return PredictResponse.model_validate(
        {"inputs": INPUTS, "eligible_categories": ["Open", "OBC"], "options": options,
         "option_count": len(options), "institutes_in_scope": scope, "unplaced_no_state": 0,
         "best_in_scope": best, "empty_message": empty}
    )  # fmt: skip


GOOD = [
    option("Alpha Medical\nCollege, Somewhere", 1, [cell("Open", "600", 4, 3, 9)]),
    option("Beta Medical College", 2, [cell("OBC", "700", 1, 4, 2)]),
]


def test_exact_match_passes():
    r = check_prediction(Q, response(GOOD))
    assert r.passed, r.failed
    assert (r.precision, r.recall) == (1.0, 1.0)


def test_extra_option_fails_precision_and_count():
    extra = [*GOOD, option("Gamma Medical College", 3, [cell("Open", "800", 2, 5, 1)])]
    r = check_prediction(Q, response(extra))
    assert {"precision", "option_count", "must_not_contain"} <= set(r.failed)
    assert r.recall == 1.0 and r.precision < 1.0


def test_missing_option_fails_recall():
    r = check_prediction(Q, response(GOOD[:1]))
    assert {"recall", "option_count", "cells"} <= set(r.failed)
    assert r.recall == 0.5 and r.precision == 1.0


def test_cell_value_or_provenance_mismatch_fails_cells():
    changes = [("closing_rank", "601"), ("allotments", 5), ("page", 99), ("line", 1), ("file", "r2.pdf")]
    for field, value in changes:
        bad = copy.deepcopy(GOOD)
        bad[0]["cells"][0][field] = value
        assert "cells" in check_prediction(Q, response(bad)).failed, field


def test_missing_round_or_zero_allotments_fails_rule_g():
    bad = copy.deepcopy(GOOD)
    bad[1]["cells"][0]["round"] = 2
    assert "round_and_allotments_named" in check_prediction(Q, response(bad)).failed
    bad = copy.deepcopy(GOOD)
    bad[1]["cells"][0]["allotments"] = 0
    assert "round_and_allotments_named" in check_prediction(Q, response(bad)).failed


def test_scope_mismatch():
    assert "institutes_in_scope" in check_prediction(Q, response(GOOD, scope=6)).failed


EMPTY_Q = {
    **Q,
    "expected_option_count": 0,
    "institutes_in_scope": 3,
    "expected_values": [{"value": 321, "allotments": 2, "file": "r1.pdf", "page": 8, "line": 7}],
    "must_not_contain": [],
}
BEST = {"institute": "Delta", "category": "Open", "round": 1, "closing_rank": "321", "allotments": 2,
        "file": "r1.pdf", "page": 8, "line": 7, "source_sha256": "0" * 64}  # fmt: skip


def test_empty_result_with_matching_best_in_scope_passes():
    r = check_prediction(EMPTY_Q, response([], scope=3, best=BEST, empty="No institute ..."))
    assert r.passed, r.failed


def test_empty_result_checks():
    assert "best_in_scope" in check_prediction(EMPTY_Q, response([], scope=3, best={**BEST, "line": 8},
                                                                 empty="m")).failed  # fmt: skip
    assert "best_in_scope" in check_prediction(EMPTY_Q, response([], scope=3, best=None, empty="m")).failed
    assert "best_in_scope" in check_prediction(EMPTY_Q, response([], scope=3, best=BEST)).failed  # no message
    r = check_prediction(EMPTY_Q, response(GOOD[:1], scope=3, best=BEST, empty=None))
    assert {"option_count", "best_in_scope"} <= set(r.failed)


def test_routing_refuse_goes_to_ask():
    assert uses_predictor(Q)
    assert not uses_predictor({**Q, "expected_behavior": "refuse"})
    assert not uses_predictor({"category": "answerable", "expected_behavior": "answer"})


def test_score_table_has_endpoint_and_pr_but_no_figures():
    rows = [
        {"id": "p-01", "category": "predictor", "endpoint": "/predict", "result": "pass", "failed": [],
         "precision": 1.0, "recall": 1.0, "latency_s": 0.01},
        {"id": "a-01", "category": "answerable", "result": "fail", "failed": ["verifier"], "latency_s": 2.0},
    ]  # fmt: skip
    meta = {"run_at": "t", "model": "m", "golden": "g", "median_latency_s": 2.0, "tokens_per_s": 1.0}
    table = score_table(rows, meta)
    assert "| p-01 | predictor | /predict | pass |  | P 1.00 / R 1.00 |" in table
    assert "| a-01 | answerable | /ask | fail | verifier |  |" in table
