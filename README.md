# cgprr-neet-rag

A private, locally hosted assistant for NEET-UG counselling questions, answered from public
documents of the Medical Counselling Committee (MCC) for the 2025 All India Quota counselling,
plus a rule-based college predictor.

- Ask: a question in plain English about closing ranks, rounds, quotas and categories. The answer
  states only figures read from Postgres rows and cites each one to its source file, page and line.
- Predictor: rank, category, PwD status, quota, course, round and (optionally) state in, a list of
  institutes whose 2025 closing rank in that round was at or above the rank out. The options are
  computed in SQL and plain code; no language model is involved.
- Every number comes from Postgres, never from the model. A citation verifier rejects any answer
  that states a number not present in a cited row, and the answer becomes a template built from
  the same rows, or a refusal.
- The language model runs locally through an OpenAI-compatible endpoint (Ollama on the Mac). No
  cloud LLM is used.

Source: Medical Counselling Committee (MCC), Government of India, mcc.nic.in

The design is described in [docs/design_note.md](docs/design_note.md). The project rules below
are referred to by letter in code comments and docs.

## Project rules

a. Numbers come from Postgres, never from the model. Ranks, seats and counts are read from SQL
   rows; the model may phrase and explain a number but never computes or recalls one.

b. Every answer cites source rows. If a number in an answer is not present in a cited row, the
   answer becomes a refusal. The citation verifier in the answer service enforces this.

c. No cloud LLM on the main path. Only the local OpenAI-compatible endpoint set in
   `LLM_BASE_URL` is used.

d. Public data only, and nothing derived from MCC's files is committed. Derived tables are
   rebuilt locally from MCC's own files.

e. The pre-registered evaluation set is read-only once locked. `scripts/check_golden_lock.py`,
   run in CI, fails if questions.yaml changes after the lock.

f. Commits carry the author's name only.

g. Closing rank is per round. Every closing-rank figure names its round and the number of
   allotments behind it. A round with no allotment in a cell has no closing rank, and no figure
   is carried over from another round.

Retrieved text is treated as data, never as instructions: text that looks like instructions to
the model is dropped before it reaches the model, the model has no tools, and every query is
fixed, parameterised SQL chosen by code. Services read the database through a read-only role and
bind to 127.0.0.1. Unit tests use fakes and never call a real model or the network; the citation
verifier has tests for a matching number, a missing number, numbers in different formats and an
answer with no citations.

## Hardware used

Development and all recorded runs used one machine (details as recorded in
[docs/benchmark.md](docs/benchmark.md)):

- Apple M5, 16 GB unified memory, macOS 26.6.2
- Ollama 0.40.16, running natively (Docker on macOS has no Apple GPU access)
- Generation model `qwen2.5:7b-instruct` (Q4_K_M), embedding model `bge-m3` (F16)

The assumed production target is a single NVIDIA RTX 6000 Ada (48 GB) serving the same models
through vLLM. Figures for that target are estimates, not measurements; they are in
[docs/benchmark.md](docs/benchmark.md).

## Quick start on macOS (no Docker)

Prerequisites: Homebrew, [uv](https://docs.astral.sh/uv/), Node.js with npm (for the web UI),
and `pdftotext` from poppler (used by the ingest parser).

```bash
brew install postgresql@18 pgvector ollama poppler node
brew services start postgresql@18
brew services start ollama            # or run `ollama serve` in a separate terminal
ollama pull qwen2.5:7b-instruct
ollama pull bge-m3

uv sync                               # Python 3.12 workspace
cp .env.example .env                  # set the passwords; see below
make migrate                          # scripts/migrate.sh: database "neet", schema, extensions, roles
scripts/check_roles.sh                # optional: proves neet_ingest / neet_reader permissions

scripts/fetch_sources.sh              # downloads the MCC PDFs into data/raw/mcc/2025/, checks sha256
make ingest                           # parse the PDFs into Postgres, with provenance per row
make index                            # embed the text chunks with bge-m3 into pgvector
make report                           # optional: parser reconciliation checks

make serve                            # retrieval :8001, answer :8002, predictor :8003 on 127.0.0.1
cd services/web && npm ci && cd ../.. # first time only
make web                              # Vite dev server
```

Then open http://127.0.0.1:5173. `make stop` stops the three services; their logs are in
`logs/<service>.log`.

Settings in `.env` for Homebrew Postgres: `POSTGRES_HOST=localhost`, `POSTGRES_HOST_PORT=5432`,
and `POSTGRES_USER` set to your macOS user (the local superuser, used only by migrations). Set
`POSTGRES_PASSWORD`, `NEET_INGEST_PASSWORD` and `NEET_READER_PASSWORD`. The services connect as
`neet_reader` (read-only); only the ingest job uses `neet_ingest`. Homebrew's default
`pg_hba.conf` trusts local connections, so role passwords are not checked there; role privileges
are. The LLM defaults (`LLM_BASE_URL=http://localhost:11434/v1`, `LLM_MODEL=qwen2.5:7b-instruct`,
`EMBED_MODEL=bge-m3`) match a local Ollama.

`make up` and `make ui` are placeholders that print TODO. The Streamlit app in `services/ui` is a
stub; the user interface is the web app in `services/web`.

## Linux and Docker Compose

`docker-compose.yml` provides Postgres 18 with pgvector (`pgvector/pgvector:0.8.7-pg18`), bound to
127.0.0.1:

```bash
cp .env.example .env                  # set POSTGRES_PASSWORD and the role passwords
docker compose up -d postgres
make migrate
```

The remaining steps are the same as on macOS (`fetch_sources.sh`, `make ingest`, `make index`,
`make serve`, `make web`). Caveats:

- The language model is not in the compose file. Run Ollama natively and point `LLM_BASE_URL` at
  it. A vLLM service for NVIDIA GPUs (`--profile gpu`) is planned; it is present in
  `docker-compose.yml` only as a commented-out block. Switching runtimes is a change of
  `LLM_BASE_URL` and `LLM_MODEL`.
- The `web` profile (`docker compose --profile web up -d --build web`) builds the web UI behind
  nginx and proxies to the answer and predictor services on the host through
  `host.docker.internal`. That works with Docker Desktop (macOS, Windows). On Linux it does not,
  because the services bind to 127.0.0.1 only and `host-gateway` resolves to the bridge address.
  On Linux use `make web`, or run the image with `network_mode: host` as described in the comment
  in `docker-compose.yml`. The binds are never widened.
- The compose file is validated in CI, not on the development Mac.

## Using Ask and Predictor

Ask handles questions about NEET-UG 2025 MCC counselling data: the closing rank of a cell
(institute, course, quota, allotted category, round), how many allotments are behind it, and
whether a stated AIR was inside that closing rank. Examples shown in the UI:

- "In NEET-UG 2025 MCC counselling, what was the Round 1 closing rank for MBBS at AIIMS New Delhi
  under the Open Seat Quota, Open category?"
- "My AIR is 9000. Was that within the Round 1 All India Open closing rank for MBBS at Madras
  Medical College?"

Each reply has one of three statuses.

- Answered: the text names the round and the number of allotments behind every closing rank, and
  each figure is followed by a source marker that opens the cited row (file, page, line, sha256).
  When the question gives the asker's own AIR, a sentence computed in code states whether it was
  inside the closing rank, followed by a note that this is not a prediction.
- Clarify: the institute name matches several institutes (for example two campuses with the same
  name). The UI lists the candidates as buttons; picking one re-asks for that institute.
- Refused: the question is outside the sources (another year, a PG or AYUSH course, a round other
  than 1 to 3 such as stray or mop-up, an institute not in the files), asks for the system
  prompt, has no matching rows, or no draft or template passed the verifier.

When a question asks for certainty ("will I definitely get", "guarantee", "sure shot"), every
reply starts with the fixed line "No one can guarantee an allotment; past closing ranks only show
what happened in 2025."

Predictor inputs are AIR (a whole number), candidate category (General, OBC, EWS, SC, ST), PwD,
quota, course, round and an optional state. The rule is fixed: an institute is listed when some
eligible allotted category (Open for General, Open plus the own category otherwise, and the PwD
variants when PwD is set) had a closing rank in the chosen round at or above the AIR. Each
option lists its cells with round, allotments and source line. State comes from MCC's Round 1
seat matrix, never from address text; institutes without a seat-matrix state are counted as not
placed rather than guessed. CW and NRI allotments are excluded. Every result carries the note
"Based on 2025 data only; not a prediction or a guarantee." When nothing qualifies, the reply
shows the best closing rank in scope instead of an empty list.

The Evidence page lists the source files with their sha256 values and the evaluation summary.

## Tests, evaluation and benchmark

```bash
make test        # uv run pytest -q (unit tests use a fake LLM client; DB/LLM integration tests skip if absent)
make lint        # ruff check and ruff format --check
make eval        # needs make serve; scores eval/golden and writes eval/results/score_table.md
make bench       # needs make serve; latency, tokens/s, embedding throughput, /predict latency
make web-check   # web UI contrast check and Playwright self-check (needs make serve; starts the dev server itself)
```

`make eval` checks the golden lock (`eval/golden/LOCK.json`) first, re-runs the citation verifier on
every returned answer, and writes raw answers to `eval/results/runs/` (gitignored). `make bench`
writes JSON to `eval/results/bench/` (gitignored) and prints a markdown summary; the recorded
results are in [docs/benchmark.md](docs/benchmark.md).

## Data source

The ten files are the NEET-UG 2025 All India Quota allotment results for Rounds 1 to 3, the Round 1
seat matrices (All India Quota except central universities; AIIMS, BHU and JIPMER; central
universities; deemed universities; ESIC insured persons) and two MCC notices about the Round 2
result. URLs, retrieval times, sizes, page counts and sha256 values are in
[data/raw/MANIFEST.md](data/raw/MANIFEST.md). How the tables are laid out and parsed, and how
closing rank is defined (per round, never carried over), is in
[docs/source_notes.md](docs/source_notes.md).

MCC's material is not redistributed in this repository; scripts/fetch_sources.sh downloads it from mcc.nic.in and verifies each file's sha256.

No table derived from the files is committed either: closing-rank tables are rebuilt locally by
the ingest job, and `data/derived/` is gitignored.

Source: Medical Counselling Committee (MCC), Government of India, mcc.nic.in

## Evaluation summary

- Pre-registered set: 18 questions (answerable, out of index, injection, unsafe advice,
  predictor), locked by sha256 in `eval/golden/LOCK.json` before the answer code was written. The
  latest run passed 18 of 18 ([eval/results/score_table.md](eval/results/score_table.md), run
  20261121T115344Z). The same set was also used during development, and every change made after
  seeing a result is logged in [docs/eval_log.md](docs/eval_log.md), so this is not a held-out
  score.
- Unseen probes: 12 questions not in the golden set, written outside the development loop, exposed
  several faults (false ambiguity from address text, comparison wording, the asker's own AIR read
  as a false premise, PG detection, prompt-leak requests, guarantee questions, unknown institutes).
  The fixes are general code with tests that use the probe texts; see the "unseen-probe fixes"
  section of [docs/eval_log.md](docs/eval_log.md).
- Blind questions: 5 questions from a person not involved in the project
  ([eval/blind/questions.txt](eval/blind/questions.txt)), committed before any was run and run once
  with no code or configuration changes. None of the five replies gave a figure, so none gave
  a wrong one, but all five were rated unhelpful: four got the same generic clarify asking for an
  institute, and the fifth (about bonds) got an advice reply that did not address the question.
  Details in [eval/blind/results.md](eval/blind/results.md).
- Latency and throughput ([docs/benchmark.md](docs/benchmark.md), 20 timed /ask requests on the
  Apple M5): p50 8.52 s, p95 25.84 s, mean 10.49 s, 97.8% of /ask time spent in the LLM, 9.3
  tokens/s generation rate including prompt processing; /predict p50 0.006 s. The run was
  disturbed: swap use was 17.0 GB of 18.4 GB just after it, memory pressure on the 16 GB machine
  is the likely cause, and the p95 and mean are inflated by it. Figures for the RTX 6000 Ada in
  the same file are estimates, not measurements.

## Known limits

- An acronym that matches only address text ("MAMC" against an address containing "MAMC
  Complex") can resolve to the wrong institute when no institute matches it by name.
- A UG question that only mentions PG ("After MBBS I want to do PG ...") is refused as a PG
  question.
- "Government Medical College Nagpur" gets a clarify (which institute?) instead of an answer,
  because a rival name with extra words ties on coverage.
- A question that combines a request for the system prompt with a data question is refused
  outright; the data part is not answered.
- Slot extraction (quota, course, category) by the model is fragile; the resolver and the cell
  lookup recovered in the recorded runs, but labels have been seen mislabelled.
- Wording is not identical between runs even at temperature 0. The figures and citations are
  checked on every run; the phrasing around them can change.
- 126 of 600 institutes have no seat-matrix state: 88 with only Deemed/Paid Seats Quota
  MBBS/BDS cells (the deemed seat matrix has no state column), 29 with MBBS/BDS cells in other
  quotas such as ESIC IP (their seat matrix layout carries no state), and 9 nursing-only
  institutes (the B.Sc. Nursing seat matrix is not among the source files). With a state filter
  the predictor counts them as not placed; it never guesses a state from address text. Counts and
  queries: [docs/source_notes.md](docs/source_notes.md), section 6.
- Only 2025 data, only Rounds 1 to 3 of the All India Quota; stray-vacancy rounds and fees are
  not in the sources.
- Open items recorded in [docs/eval_log.md](docs/eval_log.md): "Was AIR X within
  the Round N closing rank" is answered as a plain lookup, without the code-built Yes/No
  comparison; with several cited rounds the comparison line repeats per round and an absent later
  round is not mentioned; the guarantee filter rejects some negated wording and falls back to the
  template; lowercase "ms"/"dm" inside an unknown institute name triggers the PG refusal.
- From the blind questions ([eval/blind/results.md](eval/blind/results.md)): Ask has no route to
  the predictor, so "which college can I get at my rank" gets a clarify instead of a pointer to
  the Predictor; there is no out-of-scope refusal that names fees, bonds or state-quota rules,
  which are not in the data; there is no path for definition questions ("what is the category
  rank?", "what is state preference?"); and the clarify is one fixed text that does not adapt to
  what is missing.

## AI tools used

I used Claude Code (Anthropic) as a coding assistant to write and test much of the implementation, and Claude for discussion during development. I defined the scope and requirements, chose the data sources and design, reviewed the changes, and verified the results against MCC's source documents myself. I can walk through any part of the code and the decisions behind it.

## Screenshots

Demo video: https://youtu.be/ZhSCbwnk7AU

Screenshots are not committed because they show MCC figures.
