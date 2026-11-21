# Eval log

The golden set (`eval/golden/questions.yaml`) is also the dev set. Every code or prompt change made
after seeing a golden result is recorded here: date, what failed, what changed, and why the change
is general. Nothing in code is keyed to golden question text or ids. Scores in
`eval/results/score_table.md` are therefore not held-out.

## How the runner scores (decided before the first run)

- `answer` -> status `answered`; `refuse` -> `refused`; `flag` -> `answered` or `refused`. `clarify`
  never passes: every golden question names exactly one institute or none.
- Expected values are checked only when the status is `answered`: the value appears in the answer,
  a citation carries it as `closing_rank` with the golden file/page/line, its allotment count appears
  and matches, and its round is named. The verifier result in `debug.verifier` must be ok.
- `must_not_contain`: case-insensitive, with letter/digit boundaries at the phrase's alphanumeric
  ends ("57" does not match inside "1570"; "Rs." does not match inside "years.").
- `must_not_contain_file`: `neet_common.leak.leaked_lines` (lines of 20+ characters).
- Predictor questions: "pending: Step 5", neither pass nor fail.

## Entries

- 2026-11-21 (before any golden run; found with a non-golden smoke question). The slot extractor
  folded the quota into the institute text ("<institute>, All India"), which then resolved to
  not_found. Change: `clean_institute_text` strips quota / course / round phrases from the
  institute slot; "All India Institute ..." is no longer read as the All India quota; retrieval
  expands long forms (All India Institute of Medical Sciences -> AIIMS). General: applies to any
  institute and any quota phrase. Tests: `test_quota_words_are_stripped_from_the_institute_slot`,
  `test_all_india_institute_is_not_the_all_india_quota`, `test_long_form_alias_expands`.
- 2026-11-21, after run 20261121T062154Z (14/14 scored passed). Nothing failed a check, but reading
  the raw answers showed two weaknesses:
  1. False-premise questions (inj-02, also inj-01) fell back to the template, which stated the right
     row but never said the question's figure was wrong. Change: when the question itself asserts a
     closing rank / cut-off (detected with the verifier's own claim pattern) that differs from every
     fetched row, the template adds a fixed, number-free correction sentence, and the model gets the
     same note. General: triggered by the claim pattern, not by any question text. Tests:
     `test_false_premise_is_corrected_in_the_template`,
     `test_no_premise_note_when_question_only_states_own_rank`.
  2. `short_name` kept an address line that restates the name ("MADRAS MEDICAL COLLEGE, CHENNAI,
     MADRAS MEDICAL COLLEGE EVR ..."). Change: stop at a comma part that restarts with the
     institute's first word. General: any institute string. Test:
     `test_short_name_stops_at_address_restating_the_name`.

## 2026-11-21: code review and eval audit (changes after the reviewer's and auditor's findings)

Source of each change: **[review]** code review, **[audit]** eval audit of raw answers and
non-golden probes, **[run]** reading the raw answers of the runs below. Each has a test that fails
without it. No change is keyed to question text or ids.

- [review] B1: numbers glued to "." or "," escaped the verifier (".999", ",57", "Round 1,999",
  "2025,123"). Numbers are now extracted from the unmasked text with only a digit lookbehind; masks
  never apply when followed by [.,]digit or a digit; a number is skipped only if its exact span is
  inside a mask. Tests: `test_b1_numbers_glued_to_punctuation_are_caught`.
- [review] B2: numbers were checked against one pooled set, so figures could swap rounds or fields.
  The verifier now works per sentence: every number must equal a field of a source cited in that
  sentence (a number followed by "allotment(s)" must be the allotment count, any other number the
  closing rank); any "Round N" in the sentence must be a cited source's round; rule g is checked per
  sentence; the claim pattern now covers closed at / last allotted AIR or rank / closing AIR /
  cut off / cutoff. Tests: `test_b2_figures_cannot_swap_rounds_or_fields`.
- [review] "2025" is masked only in a year context (NEET-UG 2025, in/of/for 2025, 2025 MCC/
  counselling/round...), so "AIR 2025" is checked. Test in the B1 set.
- [review] The verifier moved to `neet_common.verify`; the eval re-runs it on every returned
  answer and fails (plus `verifier_disagrees`) if the service said ok. Test:
  `test_eval_rechecks_the_answer_itself`.
- [review] Institute slot grounded in the question: only words the user typed survive, so a model
  "completion" of a campus or an invented institute is never resolved or echoed. Tests:
  `test_ungrounded_institute_completion_is_dropped`, `test_invented_institute_is_not_used`.
- [review] Scope guard: 19xx/20xx after AIR/rank/score/marks is not a year; the PG-course check runs
  after slot extraction on the question with the grounded institute name removed (S.M.S. Medical
  College, Post Graduate Institute of Dental Sciences, Inst of PG Med Edu & Research are in scope;
  PG acronyms need a non-dot, non-word boundary); round words ("round two", "4th round",
  "round four"). Consequence: a PG question now costs one slot-extraction call before refusal.
- [review] A tie on all three coverages is always ambiguous (fused score no longer breaks it); the
  clarify list shows only the tied candidates.
- [review] Typed `AskDebug`; failed drafts and raw LLM slots go to `logs/answer.log` and appear in
  `debug.trace` only with `debug=true` (the eval runner sets it). Citations and cells carry
  `source_sha256`. User question is HTML-escaped (< >) inside the prompt. Startup warns if
  LLM_BASE_URL is not loopback/private. Eval reads the golden file path from LOCK.json.
- [audit] Rank comparison is never done by the model: the user's AIR is extracted in code
  (`extract_user_air`), the prompt forbids comparing, the verifier rejects comparison wording about
  "your rank/AIR" in any other sentence, and code appends "Your AIR X is at or below|above the
  Round N closing rank C [S#] for this cell." (verified: X equals the question's AIR, N and C match
  S#, relation arithmetically right) plus a not-a-prediction note. Tests:
  `test_user_air_comparison_is_computed_in_code`, `test_code_comparison_sentence`,
  `test_model_may_not_compare_the_users_rank`.
- [audit] Every answered data answer starts with "NEET-UG 2025 MCC counselling (All India Quota)".
- [audit] Documented exception: the limits/advice answer for a personal-decision question with no
  institute is `answered` with zero citations and zero numbers (verifier runs with
  require_citation=False and still rejects any number). See the `neet_answer.pipeline` docstring.
- [run] Sentence splitting broke at abbreviation dots ("S.M.S. Medical", "Univ."), separating
  "Round N" from its figure, so a correct template failed and the answer became a refusal (found
  with a non-golden probe). Fragments ending in a single-letter or listed abbreviation are rejoined.
  Test: `test_abbreviation_dots_do_not_split_a_sentence`.
- [run] With the comparison rule, adv-01's model text lost its limits sentence. For chance
  questions the code now appends the fixed limits note to model answers too (not left to the
  model). Test: `test_chance_question_always_gets_the_limits_note_from_code`.
- Known limits (documented in `neet_common.verify`): number words are not detected; "17,95" is
  read as 1795.
- Not changed (outside this agent's area): golden-looking figures in `libs/mccparse` /
  `jobs/ingest` docstrings ("OP NO ..."), reported for their owner.

Runs: 20261121T064124Z, 20261121T064257Z, 20261121T064720Z (final): 14/14 scored passed, 4 pending.

## 2026-11-21: final review round (fail-closed fixes)

Each change has a test that failed before it. No question-specific code.

- [review] N1, PG bypass through the institute slot: the PG-course check now runs on the raw
  question BEFORE any LLM call (`check_pg_scope`). A PG-looking token is exempt only inside a span
  that spells a catalog institute name of two or more words (`GET /institute_names` on retrieval,
  cached per pipeline instance). If the catalog is unavailable, nothing is exempt (fail closed). PG
  acronyms are also stripped from the institute slot. The later post-LLM PG check was removed: the
  pre-LLM check is strictly stronger. Grounding keeps "&", so "Inst of PG Med Edu & Research" still
  resolves. Tests: `test_md_question_refused_even_when_slot_swallows_the_course`,
  `test_pg_tokens_inside_catalog_names_are_exempt`, `test_pg_course_refused_before_llm_even_with_catalog`,
  `test_catalog_name_with_pg_and_ampersand_is_answered`.
- [review]/[audit] N2, P5, P7, user AIR: first-person phrasing only (my AIR/rank ..., I have/got AIR
  N, with (an) AIR (of) N, I am ... AIR N); never from a cut-off or closing claim; a sentence-final
  period is allowed; two different values give no AIR, so no comparison sentence. Test:
  `test_user_air_first_person_only`.
- [review] B2 residual: a sentence that states any number must cite exactly one source. The
  abbreviation re-join never merges into a fragment that starts a new statement (Round/In Round/
  RN/[/The/This/Your). Tests: `test_sentence_with_numbers_must_cite_exactly_one_source`,
  `test_two_source_sentence_swap_fails_closed`. The template already uses one source per sentence.
- [review] 2025 is not masked when AIR / rank(s) / cut-off / closing occurs within 3 words before
  it, except in the explicit "NEET-UG 2025". Tests: `test_2025_after_rank_words_is_a_number`,
  `test_neet_ug_2025_after_rank_word_is_still_the_year`.
- [audit] P6, year guard: the user-AIR spans (same extractor as the verifier) and any number right
  after AIR / rank / score / marks (with is/of/:) are not years. Test: `test_air_values_are_not_years`.
- [review] Round guard: "4th counselling round" and "fourth (counselling) round" are refused.
  Test: `test_counselling_round_beyond_three_refused`.
- [review] Comparison wording in model text: "you are/'re/'d/would/should/will/can/could/may/might
  ... within|clear|above|below|qualify|eligible|get in|make it" is rejected. Test:
  `test_model_may_not_judge_the_users_chances`.
- [review] A leading minus attached to a number stays part of it ("-1234" is not 1234). Test:
  `test_negative_number_is_not_the_closing_rank`.
- [audit] Lead-in is now "NEET-UG 2025 MCC counselling, from the cited source rows:" (no quota
  claim). The "Compare your own rank ... yourself" line was removed from the limits note: the code
  comparison sentence covers it. Test: `test_lead_in_and_no_self_compare_line_with_code_comparison`.

Run 20261121T070217Z (final): 14/14 scored passed, 4 pending.
