# Eval log

The golden set (`eval/golden/questions.yaml`) is also the dev set. Every change to code or to the answer
service's instruction file (`services/answer/prompts/system.txt`) made after seeing a golden result is recorded here: date, what failed, what changed, and why the change
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

## 2026-11-21: code review and eval audit

Source of each change: [review] code review, [audit] eval audit of raw answers and
non-golden probes, [run] reading the raw answers of the runs below. Each has a test that fails
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
- [review] Institute slot grounded in the question: only words present in the question survive, so a model
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
  `source_sha256`. The question text is HTML-escaped (< >) inside the model input. Startup warns if
  LLM_BASE_URL is not loopback/private. Eval reads the golden file path from LOCK.json.
- [audit] Rank comparison is never done by the model: the AIR stated in the question is extracted in
  code (`extract_user_air`), the instruction file `services/answer/prompts/system.txt` forbids
  comparing, the verifier rejects comparison wording about
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
- Golden-looking figures in the `libs/mccparse` docstrings ("OP NO 48") were changed to an
  invented "OP NO 37" (`seat_matrix.py`, `seat_cells.py`). (Corrected 2026-11-21: this line
  previously said they were not changed.)

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
- [audit] P6, year guard: user-AIR spans (same extractor as the verifier) and any number right
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

## 2026-11-21: unseen-probe fixes (Step 4.1)

Found by an independent check with 12 unseen questions (not golden questions). Each fix is general
code; no institute name or question text is special-cased. Integration tests use the exact probe
texts (`tests/test_answer_integration.py::test_probe_*`, skip without DB/LLM).

- [unseen-probe] False ambiguity from address text ("AIIMS Jodhpur" vs AIIMS Bathinda, whose
  address contains "Jodhpur Romana"). The resolver now scores the name part first: the display
  string is cut at the MCC name/address join (a comma with no space after it, or a space before
  it), and the "core name" is the head plus the last comma part of the name (the campus city).
  Order: core, head, name part, then full string (address only breaks ties). Ambiguous only when
  all four tie. Bare "Kasturba Medical College" and "JIPMER" stay ambiguous; "AIIMS Jodhpur",
  "JIPMER Puducherry", "Kasturba Medical College Manipal" resolve. Expectation change:
  "Kasturba Manipal" (previously asserted ambiguous) now resolves to the Manipal campus. Tests:
  `test_city_in_another_institutes_address_is_not_ambiguous`,
  `test_campus_city_resolves_when_head_is_shared`, `test_shared_name_without_city_stays_ambiguous`,
  `test_resolver_flags_shared_names`, `test_probe_b_name_not_address`.
- [unseen-probe] Comparison wording. The code-built sentence now answers directly: "No. Your AIR X
  is a larger number than the Round N closing rank C [S#], so in 2025 this cell was fully allotted
  before reaching your rank." / "Yes. Your AIR X is at or better than ... so in 2025 a candidate
  with a rank like yours was allotted this cell." It comes first, right after the lead-in, then
  the "not a prediction" note, then the body. Verifier rule f updated: exact form, arithmetic
  check, the Yes/No sentence must precede it and agree; a bare "Yes."/"No." anywhere else fails
  (stricter than before). Tests: `test_outside_comparison_reads_as_no`,
  `test_comparison_verdict_must_match_and_bare_yes_no_fails`,
  `test_multi_cell_comparisons_are_checked_per_cell`, `test_comparison_within_reads_yes_and_comes_first`,
  `test_probe_g_comparison_says_no_first`.
- [unseen-probe] False-premise check fired on the asker's own AIR ("closing rank ...? My AIR is
  20,100"). New `neet_common.verify.question_claims`: only values the question asserts as a
  cut-off ("the closing rank was X", "cut-off is X", "X was the closing rank"); never a user-AIR
  span, never across ?/!/sentence end or first-person words. Tests:
  `test_question_claims_only_for_asserted_cutoffs`, `test_users_own_air_is_not_a_false_premise`,
  `test_probe_h_own_air_is_not_a_premise`, `test_probe_d_false_premise_not_affirmed`.
- [unseen-probe] Requests to reveal the answer service's system prompt / instructions are refused with a fixed decline
  that offers NEET-UG 2025 counselling-data questions, before any LLM call. Counselling "rules"
  questions are not caught. Tests: `test_prompt_leak_requests`,
  `test_counselling_rules_are_not_prompt_requests`, `test_prompt_request_is_refused_before_any_llm_call`,
  `test_probe_i_prompt_leak_refused`.
- [unseen-probe] Guarantee intent (surely, definitely, guarantee, will I get, sure shot ...): every
  reply (answered, clarify, refused) starts with "No one can guarantee an allotment; past closing
  ranks only show what happened in 2025." An answered reply is re-verified in full with it. Tests:
  `test_guarantee_intent`, `test_guarantee_question_starts_with_limits_on_every_status`,
  `test_probe_j_guarantee_limits_first`.
- [unseen-probe] PG guard matches course terms only (MD/MS/MDS/DNB/DM/MCh, NEET-PG, "PG
  course/seat/degree/counselling", "postgraduate course" ...), not institute names such as "Post
  Graduate Institute of Dental Sciences". Tests: `test_pg_guard_ignores_institute_names_without_catalog`,
  `test_pg_guard_refuses_course_terms`, `test_probe_f_pg_refused`, `test_probe_l_pg_named_institute_is_not_pg`.
- [unseen-probe] A clearly named institute that the slot extractor drops (it returned null for a
  fictional name) is recovered deterministically (capitalised phrase after at/in/of/for/from with
  an institution noun) and sent to the resolver, so an unknown institute is refused as not in the
  sources instead of a "which institute?" clarify. Tests: `test_institute_fallback_from_question`,
  `test_unknown_named_institute_is_refused_even_if_extractor_returns_none`,
  `test_probe_k_unknown_institute_refused`.

### Review of the unseen-probe fixes (same day)

- [review] Resolver redesigned to fail closed. 152 of 600 display names join a one-part name and
  its city with a tight comma ("GOVT. MEDICAL COLLEGE,AURANGABAD,..."), so the city fell out of
  the name part and "Government Medical College Aurangabad" resolved to a different Aurangabad
  college. Now: a short, non-address comma part after a one-part name is taken as its city;
  generic abbreviations are normalised on both sides (Govt=Government, Sce/Sci=Sciences,
  Med=Medical, Inst=Institute, Univ=University, Hosp/Hospt=Hospital, ...); every catalog
  institute is scored, not only the search hits. Ranking key is name-part, core (head + city),
  head; it resolves only with no rival: a rival ties the key, or ties name-part and core while its
  own head is entirely words from the question (a generic head), or, when the best's name does not
  explain the whole query, covers at least as much of the query in its full string. Address text
  can only lead to a clarify. Tests: `test_tight_comma_city_and_govt_abbreviation_resolve_to_the_right_college`,
  `test_generic_head_with_state_word_is_ambiguous_not_a_winner`,
  `test_address_can_only_send_to_clarify_never_pick_a_winner`, `test_resolver_flags_shared_names`.
- [review] A middle name part typed in full in the question ("Manipal Univ.") is not read as the campus
  city: "Kasturba Medical College Manipal Univ" is ambiguous; "... Manipal" still resolves. Tests:
  `test_middle_part_typed_in_full_is_not_read_as_the_city`, `test_resolver_flags_shared_names`.
- [review] Rule d: the probe integration tests no longer contain MCC figures; expected cells are
  read from Postgres as neet_reader at test time (`_db_cells`), independent of the services.
- [review] PG guard: "PG" / "post graduate" / "postgraduation" count as PG intent except when
  followed by institute-name words (Institute, Inst, College, Med, Medical Education ...); MD / MS /
  DNB / ... are case-insensitive (dots on either side never count, so "S.M.S." and "Ms." pass).
  Test: `test_pg_guard_refuses_course_terms`, `test_pg_guard_ignores_institute_names_without_catalog`.
- [review] Verifier: a sentence that opens as a verdict ("Yes, ...", "No, ...", "Sure, ...",
  "Unfortunately ...", "Definitely ...") fails unless it is the code-built comparison pair. Tests:
  `test_model_verdict_openers_fail`, `test_fixed_no_one_sentence_is_not_a_verdict`.
- [review] Institute fallback takes the last institution phrase, skips quota phrases, strips
  leading prepositions, and returns None when unsure. Test:
  `test_institute_fallback_skips_quota_phrases_and_prefers_last`.
- [review] Guarantee detector: "100% sure" / "100% chance" now match. Test: `test_guarantee_intent`.
- [review] Removed the unreachable prompt-decline branch in `_generate` / `template_answer`; "your
  guidelines for choosing a college" is no longer read as a prompt request. Test:
  `test_counselling_rules_are_not_prompt_requests`.
- Known limits (resolver): "Manipal College of Dental Sciences Manipal" is a clarify (both campuses
  have "Manipal" in their own name; a repeated query word counts once). A query made of a name
  part that is split from its city by a tight comma inside a multi-part name ("INST.OF
  MED.SCIENCES, BHU,VARANASI") is a clarify, not a resolve.

- Open after the final review and audit (not fixed in Step 4.1; all fail safe except where noted):
  - [review] An acronym that matches only address text ("MAMC" vs a "MAMC Complex" address) can
    still resolve to that institute when no candidate matches by name. Seen as a refusal for the
    wrong institute; should become not_found or clarify when the winner's name coverage is 0.
  - [review] A UG question that merely mentions PG ("After MBBS I want to do PG. ...") is refused
    as pg_course.
  - [review] The verdict-opener rule checks only sentence openings; model sentences such as "You
    can get this college [S1]." or "Your chances look good [S1]." still pass after the code-built
    comparison. Needs a second-person outcome check when a user AIR is present.
    Fixed in Step 5 (see "2026-11-21: Step 5 answer fixes").
  - [review] "Government Medical College Nagpur" is a clarify (a rival name with extra words not
    in the question ties on coverage); a regression from the fail-closed tie rule.
  - [review] Lowercase "ms"/"dm" in an unknown institute name ("MS Ramaiah") gives the PG refusal
    instead of "not in sources". Dotted initials ("B.J.", "G.S.") do not match plain "BJ", "GS".
  - [audit] Institute names starting with "Pt." (and other unlisted abbreviations) split the
    template sentence in `sentences()`, so the round is "not named" and the answer is refused
    although the cell exists. Fix: extend `_ABBREV_END` or keep institute names from breaking
    sentences; pin "PT. B.D. SHARMA PGIMS". Fixed in Step 5 (see "2026-11-21: Step 5 answer
    fixes").

## 2026-11-21: Step 5 predictor + eval runner

Written before the first scored run that includes predictor questions. How `pred-*` are scored:

- `expected_behavior: answer` (pred-01..03): the runner calls `POST /predict` on the predictor
  service (`PREDICTOR_URL`, default 127.0.0.1:8003) with the question's `inputs` exactly as locked.
  The question text is not sent anywhere; no LLM is involved. Checks (each a named failure):
  - `option_count`: `len(options) == option_count == expected_option_count`.
  - `institutes_in_scope`: equals the golden value where the question gives one.
  - `recall` / `precision`: institute set match. An expected entry matches an option when its
    `institute_match` is a substring of the option's institute name after lower-casing and removing
    all whitespace (wrap-insensitive). recall = expected entries matched by exactly one option /
    expected entries; precision = options matched by some expected entry / options. Pass needs both
    = 1. The two values are written to the score table (they are ratios, not MCC figures).
  - `round_and_allotments_named`: every cell of every option has round = the input round and
    allotments >= 1 (hard rule g: closing rank is per round).
  - `cells`: for each matched option, its cells as (category, closing_rank, allotments, file, page,
    line) equal the golden `cells` exactly (closing_rank compared as the printed text).
  - `best_in_scope` (expected_option_count 0, pred-03): options empty and `best_in_scope`
    closing_rank / allotments / file / page / line equal the single golden expected value; an
    `empty_message` must be present.
  - `disclaimer`: `note` and the MCC `source_credit` are present.
  - `must_not_contain`: the same phrase check as for /ask, applied to the displayed text of the
    response (institute names, explanations, empty_message, note).
- `expected_behavior: refuse` (pred-04): sent to `/ask` as question text and scored exactly like
  other questions (status `refused`, `must_not_contain`). Not routed to /predict: the question asks
  for a cut-off that does not exist, so the honest outcome is a refusal from the answer service.
- Latency for /predict questions is recorded but excluded from the median (it measures SQL, not
  generation); the median stays an /ask figure.

## 2026-11-21: Step 5 answer fixes

Each fix is general code; no institute name or question text is special-cased. Tests were run
against the unfixed code first and failed.

- [review] Model-written admission verdicts are rejected anywhere in a sentence, not only as an
  opener: "you can/could/will/would/may/might/'ll/'d (not) get / secure / make it", "you are
  eligible", "you qualify", "you have / stand a good|fair|high|low|... chance", "your chances are
  good|high|...". Only the code-built Yes/No comparison pair may give a verdict. A verdict draft
  falls back to the template (which carries the code-built pair). Checked, without tuning, that no
  served answer or model draft in the recorded eval runs (270 texts) or in `logs/answer.log` (229
  drafts) changes verdict under the new rule. Tests:
  `libs/common/tests/test_verify.py::test_model_verdict_phrases_fail_anywhere_in_a_sentence`,
  `test_non_verdict_sentences_still_pass`, `test_code_comparison_pair_still_passes_with_verdict_rule`,
  `services/answer/tests/test_step5.py::test_model_verdict_mid_sentence_falls_back_to_the_code_built_comparison`,
  `test_false_premise_model_answer_without_a_verdict_is_still_served`,
  `test_guarantee_model_answer_without_a_verdict_is_still_served`.
- [audit] Sentence splitting is abbreviation-aware. `sentences()` never splits (a) inside the
  institute name of a provided source row (exact string, so catalog names with "TOWN." or
  "Akola." in them stay whole), (b) after a known abbreviation in any case (Pt, Dr, St, Smt, Lt,
  Govt, Med, Inst, Univ, Uni, Coll, Sci, Scie, Sce, Dist, Distt, Opp, Hosp, ...), (c) after an
  initial or run of initials ("B.D.", "S.N.", "K."), (d) after a 2-4 letter all-capitals token
  ("PT.", "DIST.", "MED."). Real sentence ends still split ("... [S1]. The next ...", "Goa.
  Seats ..."), and a part opening as a verdict ("Yes, ...") is never glued onto the previous
  sentence. The token list came from scanning `neet.institute` display names. Tests:
  `test_institute_name_abbreviations_do_not_split_a_sentence`, `test_real_sentence_ends_still_split`,
  `test_rejoin_never_hides_a_verdict_opener`,
  `test_template_for_an_abbreviated_institute_name_is_answered_not_refused`,
  `test_model_answer_with_abbreviated_name_is_served`, integration
  `tests/test_answer_integration.py::test_probe_abbreviated_institute_name_is_answered` (expected
  cell read from Postgres as neet_reader at test time).
- [audit] Checked (golden is also the dev set): pred-04's question text already refuses with the
  no-cell message (no Round 3 cell for that quota/category; no other round substituted). No change.
- API for the web UI (no answer-behaviour change): `AskResponse.clarify_options`
  (`ClarifyOption{institute_id, label}`; filled only for institute-ambiguity clarifies, label = the
  institute name without address), `AskResponse.guarantee_note` (true when the guarantee-limits
  sentence was prepended; the sentence stays in `answer`), `AskRequest.institute_id` (pins a
  catalog institute and skips resolution only; scope guard, slots and verifier unchanged; unknown
  id is refused). Retrieval gains `GET /institutes/{id}` (catalog lookup, 404 if unknown). Tests:
  `services/answer/tests/test_step5.py` (clarify options, pinning, unknown id, scope guard with a
  pinned id, HTTP client + /ask passthrough), `services/retrieval/tests/test_institute_lookup.py`.

### Review of the Step 5 answer fixes (same day)

- [review] Blocker: a pinned `institute_id` answered for the pinned institute even when the
  question named a different one. Now, when the question names an institute, it is resolved as
  usual and the pin is used only if it is the resolved institute or one of the ambiguous
  candidates; otherwise the pin is ignored (`debug.resolve.pin_ignored`) and the named institute
  is answered, clarified or refused as normal. A pin alone decides only when the question names no
  institute. Tests (`services/answer/tests/test_step5.py`):
  `test_pin_for_a_different_institute_than_the_named_one_is_ignored`,
  `test_pin_not_among_ambiguous_candidates_still_clarifies`,
  `test_pin_with_an_unknown_named_institute_is_refused_not_answered_for_the_pin`,
  `test_unknown_pin_is_ignored_when_the_question_names_an_institute`,
  `test_clarify_then_pin_flow_answers_for_the_picked_campus`, `test_unknown_pinned_institute_is_refused`.
- [review] The verdict phrase list kept leaking. Added a structural rule on top of it: a model
  sentence (anything but the code-built comparison pair) that addresses the reader (you / your /
  yours / you're / you'd / you'll / you've) and contains an outcome word (get, got, seat, allot*,
  admi*, chance, odds, likely, likelihood, eligib*, qualif*, cut (not cut-off), make it, land*,
  secur*, realistic, placed, expect*, reach*, within, safe*) fails. Data labels are masked first
  ("N allotments", "... Seat(s) Quota", "allotted category"). Re-check against the pre-Step-5
  verifier: of 270 recorded eval-run texts (served answers and drafts) none moves from pass to
  fail (11 already-failing texts gain this error too); of 241 drafts in `logs/answer.log`, 22 hit
  the rule, and 2 distinct texts among them had passed when logged: "Your rank is higher, but this
  does not guarantee a seat ..." (a model comparison, rightly rejected) and "Past figures cannot
  predict your chances; cut-offs vary each year." (fail-closed false positive: such a draft now
  falls back to the template). Tests: `test_reader_outcome_sentences_fail` (every string from the code review),
  `test_reader_sentences_without_an_outcome_word_pass`, `test_data_labels_are_not_outcome_words`,
  `test_cut_off_is_a_data_word_but_make_the_cut_is_a_verdict`.
- [review] Nit: pinned the fail-closed merge after an all-caps word ("... [S1] for MBBS. It closed
  at X [S2]." becomes one two-source sentence with figures, so it is refused). Test:
  `test_merge_after_a_caps_word_fails_closed` (it also failed closed before the splitting change,
  for a different reason: no round named).

### Open after the Step 5 final audit (run 20261121T115344Z, 18/18 scored)
- [audit] "Was AIR X within the Round N closing rank ..." phrasing is routed as a plain closing-rank
  lookup (intent closing_rank), so the answer states the cell but no code-built Yes/No comparison.
- [audit] A guarantee question ("Will I definitely get ...") whose AIR is within the cell gets the
  bare code-built "Yes." sentence after the limits line; consider "In 2025, yes: ..." wording.
- [audit] The guarantee filter rejects negated forms ("would not have been guaranteed"), pushing
  inj-02 to the template (answer still correct). Fail-closed; relax only with tests.
- [audit] Slot extraction mislabelled quota/course/category on inj-02; the resolver and cell
  lookup recovered, but the slots are fragile.
- [audit] With several cited rounds, the "No."/"Yes." comparison line repeats once per round, and an
  absent later round is not mentioned.

## 2026-11-21: history rewrite and lock record

- Local development tooling configuration was removed from the repository and from its history,
  so every commit hash changed. The locked question file was not modified: its sha256 in
  LOCK.json still matches, and `scripts/check_golden_lock.py` passes.
- LOCK.json `oracle_commit` was updated from 71ec6c3695a8961b546140a6819d650d0b544e6b (the hash
  before the rewrite) to 5c7545d3a841c9b20ad1d6f0385d9f897f74100b, the rewritten hash of the same
  commit ("docs, eval: apply data-policy decisions and finalise golden questions").
