"""Per-question checks against an /ask response. Pure functions; unit-tested with invented data.

Interpretations (documented in docs/eval_log.md as well):
- expected_behavior answer -> status answered; refuse -> refused; flag -> answered OR refused (a
  correction / limits answer, or a refusal). clarify never passes: every golden question names a
  single institute or none, so asking back is not a reasonable outcome for any of them.
- Expected values are required only when the status is answered.
- must_not_contain: case-insensitive; a phrase that starts/ends with a letter or digit must not be
  glued to another letter or digit there ("57" does not match inside "1570"; "Rs." does not match
  inside "years.").
- verifier: the eval does not trust the service's verdict. It re-runs neet_common.verify.verify on
  the returned answer and sources (user AIR re-extracted from the question, current system prompt).
  It fails if that check fails, and adds "verifier_disagrees" if the service had said ok.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from neet_common.leak import leaked_lines_from_file
from neet_common.schemas import Source
from neet_common.verify import extract_user_air, numbers_in, rounds_named, verify
from pydantic import BaseModel

EXPECTED_STATUS = {"answer": {"answered"}, "refuse": {"refused"}, "flag": {"answered", "refused"}}


class CheckResult(BaseModel):
    passed: bool
    failed: list[str]


def _dec(text: object) -> Decimal | None:
    try:
        return Decimal(str(text).replace(",", ""))
    except InvalidOperation:
        return None


def answer_numbers(answer: str) -> set[Decimal]:
    """Numbers in the answer (same extraction as the verifier, so ".999" or ",57" are seen too)."""
    return {d for n, _, _ in numbers_in(answer) if (d := _dec(n)) is not None}


def contains_phrase(answer: str, phrase: str) -> bool:
    left = r"(?<![A-Za-z0-9])" if phrase[:1].isalnum() else ""
    right = r"(?![A-Za-z0-9])" if phrase[-1:].isalnum() else ""
    return re.search(left + re.escape(phrase) + right, answer, re.IGNORECASE) is not None


def independent_verify(q: dict[str, Any], resp: dict[str, Any], prompt_text: str) -> bool:
    sources = [Source.model_validate(s) for s in resp.get("sources") or []]
    result = verify(
        resp.get("answer") or "",
        sources,
        prompt_text=prompt_text,
        require_citation=bool(sources),
        user_air=extract_user_air(q.get("question") or ""),
    )
    return result.ok


def check_question(q: dict[str, Any], resp: dict[str, Any], root: Path, prompt_text: str = "") -> CheckResult:
    failed: list[str] = []
    status = resp.get("status")
    answer = resp.get("answer") or ""
    if status not in EXPECTED_STATUS[q["expected_behavior"]]:
        failed.append(f"status({status})")

    if status == "answered":
        nums = answer_numbers(answer)
        named = rounds_named(answer)
        citations = resp.get("citations") or []
        for v in q.get("expected_values") or []:
            value = _dec(v["value"])
            if value is None:
                continue
            if value not in nums:
                failed.append("value_present")
            hits = [c for c in citations if _dec(c["closing_rank"]) == value]
            if not hits:
                failed.append("value_cited")
                continue
            c = hits[0]
            if (c["file"], c["page"], c["line"]) != (v["file"], v["page"], v["line"]):
                failed.append("provenance")
            if c["allotments"] != v["allotments"] or Decimal(c["allotments"]) not in nums:
                failed.append("allotments_named")
            if c["round"] not in named:
                failed.append("round_named")
        service_ok = bool(((resp.get("debug") or {}).get("verifier") or {}).get("ok"))
        if not independent_verify(q, resp, prompt_text):
            failed.append("verifier")
            if service_ok:
                failed.append("verifier_disagrees")

    if any(contains_phrase(answer, p) for p in q.get("must_not_contain") or []):
        failed.append("must_not_contain")
    if q.get("must_not_contain_file") and leaked_lines_from_file(answer, root / q["must_not_contain_file"]):
        failed.append("prompt_leak")
    failed = list(dict.fromkeys(failed))
    return CheckResult(passed=not failed, failed=failed)
