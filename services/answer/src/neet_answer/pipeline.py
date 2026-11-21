"""The /ask pipeline: scope guard -> slots -> course scope -> resolve -> exact cells -> generate -> verify.

Numbers only ever come from cells fetched by fixed SQL in the retrieval service. The model phrases;
the verifier decides whether its text may be served; otherwise a template built from the same rows
is served (and verified too); with no rows the answer is a refusal. Comparisons of the user's own AIR
with a closing rank are computed here in code, never by the model.

Deliberate exception to "no citations -> refusal": a personal-decision question that names no
institute gets the fixed limits answer, status answered, with zero citations and zero numbers
(the verifier runs on it with require_citation=False and still rejects any number).
"""

from __future__ import annotations

import logging
import re
from decimal import Decimal
from typing import Any, Literal

from neet_common.llm import ChatResult, LLMError
from neet_common.safety import looks_like_instruction
from neet_common.schemas import (
    AskDebug,
    AskResponse,
    Cell,
    CellsRequest,
    ClarifyOption,
    InstituteInfo,
    ResolveRequest,
    Source,
)
from neet_common.verify import extract_user_air, question_claims, verify

from neet_answer import compose
from neet_answer.retrieval_client import Retrieval, RetrievalError
from neet_answer.scope import (
    PROMPT_REFUSAL,
    asks_for_prompt,
    asks_guarantee,
    check_pg_scope,
    check_scope,
    exclusion_terms,
    strip_pg_tokens,
)
from neet_answer.slots import ChatModel, Slots, extract_raw, normalise

log = logging.getLogger("neet_answer")

MAX_SOURCES = 12  # more matching cells than this -> ask the user to narrow the question
Status = Literal["answered", "refused", "clarify"]
# Words that name a kind of college, not a college. An institute slot made only of these is no slot.
GENERIC_INSTITUTE_WORDS = frozenset(
    {
        "a", "an", "the", "any", "some", "good", "top", "best", "my", "this", "that", "nearest", "near",
        "private", "government", "govt", "public", "deemed", "medical", "dental", "nursing",
        "college", "colleges", "institute", "institutes", "university", "seat", "seats",
    }
)  # fmt: skip
_CHANCE = re.compile(
    r"\b(?:should|will|would|can|could)\s+i\b|\bchances?\b|\bwithin\s+reach\b|\bam\s+i\s+likely\b",
    re.IGNORECASE,
)
_AIR_TEXT = re.compile(r"\d{1,3}(?:,\d{2,3})+|\d+")
UNAVAILABLE = "I can't look that up right now (the retrieval service is unavailable)."
_TRACE_KEYS = ("attempts", "raw_slots")


def _specific(institute_text: str | None) -> bool:
    words = re.findall(r"[a-z]+", (institute_text or "").lower())
    return any(w not in GENERIC_INSTITUTE_WORDS for w in words)


def _user_air_text(question: str) -> str | None:
    air = extract_user_air(question)
    if air is None:
        return None
    return next((t for t in _AIR_TEXT.findall(question) if t.replace(",", "") == str(air)), str(air))


class Pipeline:
    def __init__(self, llm: ChatModel, retrieval: Retrieval, system_prompt: str) -> None:
        self.llm = llm
        self.retrieval = retrieval
        self.system_prompt = system_prompt
        self._catalog: list[str] | None = None  # institute names, fetched once per pipeline instance

    def _catalog_names(self) -> list[str]:
        if self._catalog is None:
            try:
                self._catalog = self.retrieval.institute_names()
            except RetrievalError as exc:
                log.warning("institute names unavailable; PG check fails closed: %s", exc)
                return []
        return self._catalog

    def _reply(
        self,
        status: Status,
        answer: str,
        debug: dict[str, Any],
        sources: list[Source] | None = None,
        cited: list[str] | None = None,
        options: list[ClarifyOption] | None = None,
    ) -> AskResponse:
        srcs = sources or []
        trace = {k: debug.pop(k) for k in _TRACE_KEYS if k in debug}
        return AskResponse(
            answer=answer,
            status=status,
            citations=compose.citations(srcs, cited or []),
            sources=srcs,
            debug=AskDebug(**debug, trace=trace or None),
            clarify_options=options or [],
        )

    def _record_llm(self, debug: dict[str, Any], res: ChatResult) -> None:
        debug.setdefault("llm_calls", []).append(
            {"completion_tokens": res.completion_tokens, "seconds": round(res.seconds, 3)}
        )

    def ask(self, question: str, institute_id: int | None = None) -> AskResponse:
        """Answer `question`. `institute_id` pins a catalog institute the user picked (for example from
        clarify_options): it replaces institute resolution only; everything else runs as normal."""
        r = self._ask(question, institute_id)
        if not asks_guarantee(question):
            return r
        # Guarantee intent: every reply starts with the fixed limits sentence. An answered reply is
        # re-verified in full with it, so the prefix never bypasses the citation verifier.
        text = compose.GUARANTEE_NOTE + "\n" + r.answer
        if r.status != "answered":
            return r.model_copy(update={"answer": text, "guarantee_note": True})
        check = verify(
            text,
            r.sources,
            prompt_text=self.system_prompt,
            require_citation=bool(r.sources),
            user_air=extract_user_air(question),
        )
        if check.ok:
            return r.model_copy(update={"answer": text, "guarantee_note": True})
        log.error("guarantee-prefixed answer failed the verifier: %s", check.errors)
        return r.model_copy(
            update={
                "status": "refused",
                "answer": compose.GUARANTEE_NOTE + "\nI can't give a verified answer from the sources.",
                "citations": [],
                "sources": [],
                "guarantee_note": True,
            }
        )

    def _ask(self, question: str, institute_id: int | None = None) -> AskResponse:
        debug: dict[str, Any] = {"template": False}
        if asks_for_prompt(question):  # deterministic, before any LLM call
            debug["scope"] = "prompt_request"
            return self._reply("refused", PROMPT_REFUSAL, debug)
        scope = check_scope(question)
        if not scope.in_scope:
            debug["scope"] = scope.reason
            return self._reply("refused", scope.message or "That is not in the sources.", debug)
        pg = check_pg_scope(question, self._catalog_names())  # before any LLM call; fails closed
        if not pg.in_scope:
            debug["scope"] = pg.reason
            return self._reply("refused", pg.message or "That is not in the sources.", debug)
        try:
            raw, res = extract_raw(self.llm, question)
            raw.institute_text = strip_pg_tokens(raw.institute_text)
            self._record_llm(debug, res)
        except LLMError as exc:
            debug["error"] = f"slot extraction: {exc}"
            return self._reply(
                "refused", "I can't process questions right now (the local model is unavailable).", debug
            )
        slots = normalise(raw, question)
        debug["raw_slots"] = raw.model_dump()
        debug["slots"] = slots.model_dump()
        chance = slots.intent in ("admission_chance", "advice") or _CHANCE.search(question) is not None
        named = _specific(slots.institute_text)
        if institute_id is not None and not named:  # no institute in the question: the pin names it
            return self._pinned_answer(question, institute_id, slots, debug, chance=chance)
        if not named:
            if chance:
                return self._limits(debug)
            return self._reply(
                "clarify",
                "Which institute do you mean? I answer from per-institute closing ranks, so please name"
                " the college (and its city), plus the quota, category and round if you know them.",
                debug,
            )
        return self._data_answer(question, slots, debug, chance=chance, pin=institute_id)

    def _limits(self, debug: dict[str, Any]) -> AskResponse:
        text = compose.limits_answer()
        check = verify(text, [], prompt_text=self.system_prompt, require_citation=False)
        debug["template"] = True
        debug["verifier"] = check.model_dump()
        if not check.ok:  # only if the fixed text is edited badly; never serve it then
            return self._reply("refused", "I can't answer that from the sources.", debug)
        return self._reply("answered", text, debug)

    def _data_answer(
        self, question: str, slots: Slots, debug: dict[str, Any], *, chance: bool, pin: int | None = None
    ) -> AskResponse:
        """Resolve the institute named in the question. A pinned id is used only when it is the
        resolved institute or one of the ambiguous candidates; otherwise it is ignored, so a pin never
        answers for an institute other than the one the question names."""
        inst_text = slots.institute_text or ""  # grounded: only words the user typed
        try:
            res = self.retrieval.resolve(
                ResolveRequest(text=inst_text, exclude=exclusion_terms(question, inst_text))
            )
        except RetrievalError as exc:
            debug["error"] = str(exc)
            return self._reply("refused", UNAVAILABLE, debug)
        debug["resolve"] = {
            "status": res.status,
            "candidates": [(c.id, c.short_name) for c in res.candidates[:3]],
        }
        if pin is not None:
            allowed = (
                {c.id for c in res.candidates}
                if res.ambiguous
                else ({res.resolved_id} if res.resolved_id is not None else set())
            )
            picked = next((c for c in res.candidates if c.id == pin and c.id in allowed), None)
            if picked is not None:
                debug["resolve"]["pinned"] = pin
                return self._cells_answer(question, slots, debug, picked.id, picked.short_name, chance=chance)
            debug["resolve"]["pin_ignored"] = pin
            log.warning("pinned institute %s is not the institute named in the question", pin)
        if res.ambiguous:
            shown = res.candidates[:4]
            names = "; ".join(c.short_name for c in shown)
            return self._reply(
                "clarify",
                f'"{inst_text}" matches more than one institute in the data: {names}. Which one do you'
                " mean? I never combine figures from different institutes.",
                debug,
                options=[ClarifyOption(institute_id=c.id, label=c.short_name) for c in shown],
            )
        if res.resolved_id is None or not res.candidates:
            msg = f"{inst_text} is not in the indexed NEET-UG 2025 MCC sources, so I can't give a figure"
            msg += " for it."
            return self._reply("refused", msg, debug)
        inst = res.candidates[0]
        return self._cells_answer(question, slots, debug, inst.id, inst.short_name, chance=chance)

    def _pinned_answer(
        self, question: str, institute_id: int, slots: Slots, debug: dict[str, Any], *, chance: bool
    ) -> AskResponse:
        """The user picked a catalog institute by id: validate it exists, then answer as normal."""
        try:
            info: InstituteInfo | None = self.retrieval.institute(institute_id)
        except RetrievalError as exc:
            debug["error"] = str(exc)
            return self._reply("refused", UNAVAILABLE, debug)
        debug["resolve"] = {"status": "pinned", "institute_id": institute_id, "found": info is not None}
        if info is None:
            return self._reply(
                "refused", "That institute is not in the indexed NEET-UG 2025 MCC sources.", debug
            )
        return self._cells_answer(question, slots, debug, info.id, info.short_name, chance=chance)

    def _cells_answer(
        self,
        question: str,
        slots: Slots,
        debug: dict[str, Any],
        inst_id: int,
        inst_name: str,
        *,
        chance: bool,
    ) -> AskResponse:
        try:
            fetched = self.retrieval.cells(
                CellsRequest(
                    institute_id=inst_id,
                    quota=slots.quota,
                    course=slots.course,
                    allotted_category=slots.category,
                    include_cw_nri=slots.cw_nri,
                )
            )
        except RetrievalError as exc:
            debug["error"] = str(exc)
            return self._reply("refused", UNAVAILABLE, debug)
        cells = [c for c in fetched.cells if not self._suspicious(c)]
        in_round = [c for c in cells if not slots.rounds or c.round in slots.rounds]
        if not in_round:
            other = sorted({c.round for c in cells})
            return self._reply("refused", compose.no_cell_message(slots, inst_name, other), debug)
        if len(in_round) > MAX_SOURCES or fetched.truncated:
            return self._narrow(in_round, inst_name, debug)
        return self._generate(question, compose.make_sources(in_round), debug, chance=chance)

    def _suspicious(self, cell: Cell) -> bool:
        if looks_like_instruction(cell.institute):
            log.warning("dropped instruction-like row %s", cell.id)
            return True
        return False

    def _narrow(self, cells: list[Cell], institute: str, debug: dict[str, Any]) -> AskResponse:
        def opts(values: set[str]) -> str:
            return ", ".join(sorted(values))

        return self._reply(
            "clarify",
            f"There are many closing-rank rows for {institute}. Please narrow the question: course"
            f" ({opts({c.course for c in cells})}), quota ({opts({c.quota for c in cells})}), category"
            f" ({opts({c.allotted_category for c in cells})}) and round.",
            debug,
        )

    def _generate(
        self, question: str, sources: list[Source], debug: dict[str, Any], *, chance: bool
    ) -> AskResponse:
        user_air, air_text = extract_user_air(question), _user_air_text(question)
        stated = question_claims(question)  # asserted cut-offs only, never the user's own AIR
        premise_mismatch = bool(stated) and any(
            v not in {s.cell.closing_rank for s in sources} for v in stated
        )
        notes = []
        if chance:
            notes.append("The user asks about their own chances: state the limits, give no guarantee.")
        if user_air is not None:
            notes.append("Do not compare the user's rank with any figure; the system adds that comparison.")
        if premise_mismatch:
            notes.append(
                "The question states a closing rank that does not match the rows: say so explicitly."
            )
        if any(s.cell.is_cw_nri for s in sources):
            notes.append("Some rows are CW/NRI seats: give the CW rank / NRI priority caveat for them.")
        messages = compose.build_messages(self.system_prompt, question, sources, notes)
        attempts: list[dict[str, Any]] = []
        debug["attempts"] = attempts
        try:
            for attempt in range(2):
                if attempt == 1:
                    messages = compose.retry_messages(
                        messages, attempts[-1]["answer"], attempts[-1]["errors"]
                    )
                res = self.llm.chat(messages, max_tokens=400)
                self._record_llm(debug, res)
                body = res.content.strip()
                check = verify(body, sources, prompt_text=self.system_prompt)  # the model's own text: strict
                attempts.append({"answer": body, "errors": check.errors})
                if check.ok:
                    limits = [compose.LIMITS_NOTE] if chance else []  # never left to the model
                    final = compose.finalise(
                        body, limits, compose.comparisons(sources, check.cited, user_air, air_text)
                    )
                    served = self._serve(final, sources, debug, user_air)
                    if served is not None:
                        return served
        except LLMError as exc:
            debug["error"] = f"generation: {exc}"
        body = compose.template_answer(sources, chance=chance, premise_mismatch=premise_mismatch)
        all_ids = [s.sid for s in sources]
        final = compose.finalise(body, [], compose.comparisons(sources, all_ids, user_air, air_text))
        debug["template"] = True
        served = self._serve(final, sources, debug, user_air)
        if served is None:
            log.error("template answer failed the verifier: %s", debug["verifier"]["errors"])
            return self._reply("refused", "I can't give a verified answer from the sources.", debug)
        return served

    def _serve(
        self, final: str, sources: list[Source], debug: dict[str, Any], user_air: Decimal | None
    ) -> AskResponse | None:
        check = verify(final, sources, prompt_text=self.system_prompt, user_air=user_air)
        debug["verifier"] = check.model_dump()
        if not check.ok:
            return None
        return self._reply("answered", final, debug, sources, check.cited)
