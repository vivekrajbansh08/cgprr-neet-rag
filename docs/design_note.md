# Design note: cgprr-neet-rag

Source: Medical Counselling Committee (MCC), Government of India, mcc.nic.in

## Problem

NEET-UG counselling questions are mostly about numbers: the closing rank of a cell (institute,
course, quota, allotted category, round) and how many allotments sit behind it. A model that
recalls or computes such a number can be wrong in a way the reader cannot see. The system answers
from MCC's public 2025 documents only, runs on one local machine, and reads every figure from a
database row that it cites.

## Architecture

```
MCC PDFs (sha256-checked) -> jobs/ingest (pdftotext, libs/mccparse; file, page, line per row)
  -> Postgres schema neet: allotment, institute, chunk (pgvector), closing_rank views
       ^ read-only role neet_reader
  retrieval :8001   FTS + pgvector fused by RRF; fixed SQL cell lookup
  answer    :8002   scope guard, slots (LLM), resolve, cells, draft (LLM), verify, template or refuse
  predictor :8003   fixed SQL and a rule in code; no LLM
  web UI on 127.0.0.1                     LLM: Ollama at LLM_BASE_URL (OpenAI-compatible)
```

Closing rank is computed in SQL, per round, as the largest AIR allotted in a cell in that round. A
cell with no allotment in a round has no row, so nothing is carried over between rounds. The
retrieval service finds candidate institutes with full-text search and bge-m3 vectors fused by
reciprocal rank fusion; a deterministic resolver then picks one, asks which one is meant
(clarify), or reports not found.

Why numbers never come from the model:

- SQL-only figures. The model sees only cells fetched by fixed, parameterised SQL chosen by code.
  It has no tools and cannot run queries.
- Citation verifier (`neet_common.verify`). A sentence that states a number must cite exactly one
  source, and each number must equal that source's closing rank, or its allotment count when
  followed by "allotment(s)". Any "Round N" must match the cited round. Model-written admission
  verdicts ("you can get", "your chances are good") are rejected.
- Template fallback. A draft that fails the verifier is replaced by a template built from the same
  rows, which is verified too. With no rows, or a failing template, the reply is a refusal.
- Code-built comparisons. When the question gives the asker's AIR, the Yes/No sentence comparing it
  with the closing rank is computed in code and checked arithmetically by the verifier.
- Predictor. Options come from a fixed rule over `neet.closing_rank` rows, and the explanation is
  assembled from row fields.

Retrieved text is data: chunks sit in delimited source blocks, chunks that look like instructions
are dropped, and an injected number cannot pass the verifier. Scope checks (other years, PG
courses, rounds outside 1 to 3, requests for the system prompt) run before any model call.

## Model choice

| model | role | parameters | quantisation | context | licence |
|---|---|---|---|---|---|
| qwen2.5:7b-instruct | answer LLM | 7.6B | Q4_K_M | 32,768 | Apache 2.0 |
| bge-m3 | embeddings | 566.7M | F16 | 8,192 | MIT |

Values from `docs/benchmark.md`. Both fit in 16 GB next to Postgres; the 7B model produces
schema-constrained JSON for slot extraction, with the verifier and template covering its
mistakes; bge-m3 is multilingual. Moving to vLLM is a change of `LLM_BASE_URL` and `LLM_MODEL`;
the vLLM compose profile is planned.

## Performance and GPU memory estimate

Measured on an Apple M5 with 16 GB (`docs/benchmark.md`, 20 timed /ask requests, one at a time):
/ask p50 8.52 s, p95 25.84 s, mean 10.49 s; 97.8% of /ask time is in the LLM; generation rate 9.3
tokens/s including prompt processing; /predict p50 0.006 s. The run was disturbed: swap use was
17.0 GB of 18.4 GB just after it, memory pressure is the likely cause, and the p95 and mean are
inflated by it.

For one RTX 6000 Ada (48 GB) the same file gives estimates, not measurements, assuming about 960
GB/s bandwidth, vLLM using 0.9 of VRAM, 2.5 GB overhead, FP16 KV cache and decode at 0.6 of peak
bandwidth. The 7B model with bge-m3 at 32k context needs about 10.13 GB at 4-bit or 20.74 GB at
FP16; single-stream decode is about 125 or 38 tokens/s. A 32B model at 4-bit is the largest
option that keeps 32k contexts and bge-m3 on the card.

## Evaluation method and results

The golden set of 18 questions (6 answerable, 3 out of index, 3 injection, 2 unsafe advice, 4
predictor) has expected values derived by oracle scripts and was locked by sha256
(`eval/golden/LOCK.json`, 2026-11-20 20:49 IST) before the answer pipeline was built. Edits are
blocked once `eval/golden/.locked` exists, the runner verifies the lock before scoring, and it
re-runs the citation verifier on every answer.

The latest run passed 18 of 18 (`eval/results/score_table.md`, run 20261121T115344Z). The set was
also the development set; every change made after seeing a result is in `docs/eval_log.md`, and
no code is keyed to question text. The score is not held-out.

Two checks sat outside that loop. Twelve unseen probe questions found faults in institute
resolution, comparison wording, premise and PG detection, prompt-leak and guarantee handling;
each fix is general code with a test that uses the probe text. Five blind questions from a person
not involved in the project were committed, then run once with no changes
(`eval/blind/results.md`). None gave a figure, so none gave a wrong one, but all five were
unhelpful: four got the same fixed clarify, one an advice reply that missed the question. Missing:
a route from Ask to the predictor, a refusal naming fees, bonds or state-quota rules as out of
scope, and a path for definition questions.

## Data privacy

- Postgres, services, logs and model run locally on 127.0.0.1. No cloud LLM, cloud GPU or
  telemetry.
- The web UI self-check (`services/web/tests/selfcheck.spec.ts`) fails if any browser request
  goes to a host other than 127.0.0.1, localhost or ::1.
- Services connect as `neet_reader` (SELECT only); only ingest uses `neet_ingest`.
- Row-level data (AIR, category, PwD status, college) is quasi-identifying and stays in the local
  database. Nothing derived from MCC files is committed.
- On a site serving several businesses, each gets its own schema or database with its own roles
  and indexes, and no service holds another business's credentials. The current build has one
  schema, `neet`.

## Cost

There is no per-query charge: no cloud API or cloud GPU is used. Electricity is the running cost.
With the assumptions in `docs/benchmark.md` (₹8 per kWh as a placeholder tariff, one RTX 6000 Ada
workstation drawing about 450 W under load), that is about ₹3.60 per hour or ₹28.80 per 8-hour
day. The Mac's draw under load was not measured; one idle reading after the run was about 28.5 W.
