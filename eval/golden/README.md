# eval/golden: pre-registered eval set

Source: Medical Counselling Committee (MCC), Government of India, mcc.nic.in

| File | What it is |
|---|---|
| `questions.yaml` | The 18 pre-registered questions. **Locked. Never edited.** |
| `LOCK.json` | sha256 and question count of `questions.yaml`, lock time (IST), and the oracle commit that derived its values |
| `SPOTCHECK.md` | Three answers you can confirm by eye in the PDFs |
| `.locked` | Local marker (gitignored). While it exists, a local guard blocks writes under `eval/golden/` |

## Integrity

- `scripts/check_golden_lock.py` recomputes the sha256 and question count against `LOCK.json`
  and fails loudly on any mismatch. It runs in CI.
- `tests/test_golden_questions.py` re-derives every expected value with the independent oracle
  (`scripts/oracle_*.py`) when the raw MCC PDFs are present.
- A local guard blocks edits on `eval/golden/` and any Bash command that
  writes there (redirection, mv, cp, rm, sed -i, tee, touch, git checkout/restore, ...).
  It is a guard against accidents, not a security boundary.

## Amendment policy

After the lock, `questions.yaml` is never edited, not even to fix a typo or a value.

1. Changes go into a **new file, `questions.v2.yaml`**, which starts as a copy of `questions.yaml`.
2. The top of `questions.v2.yaml` records **each change with its date and reason**, for example
   `# 2026-12-03: pred-02 near-miss list corrected after ingest found X (reason ...)`.
3. `questions.v2.yaml` gets its own lock (a `LOCK.v2.json` with the same fields) before any
   result is reported against it.
4. Results are **reported against both** `questions.yaml` and `questions.v2.yaml`, side by side, so
   any change in score caused by the amendment is visible.
5. Never tune prompts or code against these questions and then report the score as held-out
   (project rules).
