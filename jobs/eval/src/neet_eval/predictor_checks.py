"""Checks for predictor questions answered by POST /predict. Pure functions; unit-tested with invented data.

Scoring is described in docs/eval_log.md ("2026-11-21: Step 5 predictor + eval runner"). Failed check
names: option_count, institutes_in_scope, recall, precision, round_and_allotments_named, cells,
best_in_scope, disclaimer, must_not_contain.
"""

from __future__ import annotations

import re
from typing import Any

from neet_common.predictor import PredictResponse
from pydantic import BaseModel

from neet_eval.checks import contains_phrase


class PredictorCheck(BaseModel):
    passed: bool
    failed: list[str]
    precision: float | None
    recall: float | None


def squash(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def visible_text(resp: PredictResponse) -> str:
    parts = [o.institute for o in resp.options] + [o.explanation for o in resp.options]
    parts += [resp.empty_message or "", resp.note]
    return "\n".join(parts)


def _cell_key(category: str, closing_rank: object, allotments: int, file: str, page: int, line: int) -> tuple:
    return (category, str(closing_rank), int(allotments), file, int(page), int(line))


def check_prediction(q: dict[str, Any], resp: PredictResponse) -> PredictorCheck:
    failed: list[str] = []
    expected = q.get("expected_values") or []
    want_count = q["expected_option_count"]
    if not (len(resp.options) == resp.option_count == want_count):
        failed.append("option_count")
    if "institutes_in_scope" in q and resp.institutes_in_scope != q["institutes_in_scope"]:
        failed.append("institutes_in_scope")
    if not resp.note or not resp.source_credit.startswith("Source: Medical Counselling Committee"):
        failed.append("disclaimer")
    rnd = q["inputs"]["round"]
    if any(c.round != rnd or c.allotments < 1 for o in resp.options for c in o.cells):
        failed.append("round_and_allotments_named")

    precision: float | None = None
    recall: float | None = None
    if want_count == 0:
        b = resp.best_in_scope
        ev = expected[0] if len(expected) == 1 else None
        if (
            resp.options
            or ev is None
            or b is None
            or not resp.empty_message
            or _cell_key("", b.closing_rank, b.allotments, b.file, b.page, b.line)
            != _cell_key("", ev["value"], ev["allotments"], ev["file"], ev["page"], ev["line"])
        ):
            failed.append("best_in_scope")
    else:
        matched_options: set[int] = set()
        recalled = 0
        cells_ok = True
        for ev in expected:
            hits = [o for o in resp.options if squash(ev["institute_match"]) in squash(o.institute)]
            if len(hits) != 1:
                cells_ok = False
                continue
            recalled += 1
            o = hits[0]
            matched_options.add(o.institute_id)
            got = sorted(
                _cell_key(c.category, c.closing_rank, c.allotments, c.file, c.page, c.line) for c in o.cells
            )
            want = sorted(
                _cell_key(c["category"], c["closing_rank"], c["allotments"], ev["file"], c["page"], c["line"])
                for c in ev.get("cells") or []
            )
            if got != want:
                cells_ok = False
        recall = recalled / len(expected) if expected else 1.0
        precision = (
            sum(o.institute_id in matched_options for o in resp.options) / len(resp.options)
            if resp.options
            else 0.0
        )
        if recall != 1.0:
            failed.append("recall")
        if precision != 1.0:
            failed.append("precision")
        if not cells_ok:
            failed.append("cells")

    text = visible_text(resp)
    if any(contains_phrase(text, p) for p in q.get("must_not_contain") or []):
        failed.append("must_not_contain")
    failed = list(dict.fromkeys(failed))
    return PredictorCheck(passed=not failed, failed=failed, precision=precision, recall=recall)
