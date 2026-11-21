# eval/golden: pre-registered eval set

Source: Medical Counselling Committee (MCC), Government of India, mcc.nic.in

| File | What it is |
|---|---|
| `questions.yaml` | The 18 pre-registered questions. Locked and never edited. |
| `LOCK.json` | sha256 and question count of `questions.yaml`, the lock time (IST), and the commit of the scripts that derived its values |
| `SPOTCHECK.md` | Three answers that can be confirmed by eye in the PDFs |

## Integrity

- `scripts/check_golden_lock.py`, run in CI, fails if questions.yaml changes after the lock. It recomputes the sha256 and question count against `LOCK.json`.
- `tests/test_golden_questions.py` re-derives every expected value with the scripts in `scripts/oracle_*.py` when the raw MCC PDFs are present. These scripts share the ingest parser (`libs/mccparse`), so they confirm the values but do not check the parser independently. The independent evidence (seat-matrix reconciliation, manual checks against the PDFs and re-extraction) is described in `docs/source_notes.md` section 7.

## Amendment policy

After the lock, `questions.yaml` is never edited, not even to fix a typo or a value.

1. Changes go into a new file, `questions.v2.yaml`, which starts as a copy of `questions.yaml`.
2. The top of `questions.v2.yaml` records each change with its date and reason, for example `# 2026-12-03: pred-02 near-miss list corrected after ingest found X (reason ...)`.
3. `questions.v2.yaml` gets its own lock (a `LOCK.v2.json` with the same fields) before any result is reported against it.
4. Results are reported against both `questions.yaml` and `questions.v2.yaml`, side by side, so any change in score caused by the amendment is visible.
5. A score obtained after tuning the code against these questions is never reported as an independent result (project rule e and the testing notes in the repository README).
