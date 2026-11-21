# Benchmark

Measured latency and throughput of the local stack on one Apple Silicon Mac, followed by
estimates for a single RTX 6000 Ada class workstation GPU. The Mac figures are measurements. Every
GPU figure in this document is an ESTIMATE computed from model configurations and published
hardware specifications. No cloud GPU was used, and no GPU run was made.

Source of the measured numbers: `eval/results/bench/20261121T124634Z.json` (gitignored, local
only), written by `make bench` (`uv run python -m neet_bench`).

## Setup

| item | value |
|---|---|
| machine | Apple M5 (Mac17,3), 16 GB unified memory |
| OS | macOS 26.6.2 (build 25G83) |
| LLM runtime | Ollama 0.40.16, native on macOS (Metal), OpenAI-compatible endpoint `http://localhost:11434/v1` |
| code | commit `725dcd8` with uncommitted changes in the working tree (bench job and web UI files; the answer, retrieval and predictor services were unchanged) |
| services | retrieval :8001, answer :8002, predictor :8003 (uvicorn, one worker each), Postgres 18 with pgvector on localhost |
| run window | 2026-11-21 12:46:34 to 12:50:29 UTC |

| model | role | digest | parameters | quantisation | context | licence |
|---|---|---|---|---|---|---|
| qwen2.5:7b-instruct | answer LLM | 845dbda0ea48 | 7.6B (7,615,616,512) | Q4_K_M | 32,768 | Apache 2.0 |
| bge-m3 | embeddings | 790764642607 | 566.7M (566,703,104) | F16 | 8,192 | MIT |

Both models were already loaded in Ollama when the run started.

## Method

The bench job runs three phases, one request at a time (no concurrency):

- `/ask`: questions from the locked golden set (`eval/golden/questions.yaml`, lock verified first),
  excluding predictor questions that expect an answer. The 15 eligible questions are cycled. The
  first 3 requests are warm-ups and are discarded; the next 20 are timed. End-to-end time is
  measured by the client around the HTTP call. LLM time and completion tokens come from the
  response's `debug.llm_calls`, the same accounting as the eval runner.
- Embeddings: 64 chunk texts sent to bge-m3 in one batch of 64 (the batch size the indexer uses),
  after one untimed warm-up batch.
- `/predict`: the golden predictor inputs, cycled; 3 warm-ups discarded, 50 timed.

Percentiles use linear interpolation between closest ranks: position p/100 x (n - 1) in the
sorted list (the numpy default, Excel PERCENTILE.INC). With n = 20, p95 sits between the 19th and
20th values.

Derived figures:

- LLM time share = sum of LLM seconds / sum of end-to-end seconds, over successful requests.
- Generation tokens/s = sum of completion tokens / sum of LLM seconds. LLM seconds include prompt
  processing (prefill) as well as decoding, so this is an end-to-end generation rate, lower than a
  pure decode rate.

## Measured results (Apple M5, 16 GB)

| metric | value |
|---|---|
| /ask p50 end-to-end | 8.52 s |
| /ask p95 end-to-end | 25.84 s |
| /ask mean end-to-end | 10.49 s |
| /ask outcomes (20 timed) | 13 answered, 7 refused, 0 errors; 31 LLM calls |
| LLM share of /ask time | 97.8% |
| generation rate (completion tokens / LLM seconds) | 9.3 tokens/s |
| bge-m3 embedding, 64 chunks in one batch | 2.39 s, 26.8 chunks/s |
| /predict p50 | 0.006 s |
| /predict p95 | 0.012 s |
| /predict mean | 0.007 s, 0 errors |

Four of the seven refusals took under 0.01 s because they were decided before any LLM call; they
pull the p50 down. Answered requests made one to three LLM calls each.

Almost all `/ask` time is spent in the LLM. Retrieval, SQL and the citation verifier together take
up to about 0.4 s per request. The predictor makes no LLM call and answers in milliseconds.

## RTX 6000 Ada: ESTIMATES

All figures in this section are ESTIMATES. Assumptions:

- GPU: RTX 6000 Ada, 48 GB VRAM (treated as 48 x 10^9 bytes; the card has slightly more, so
  rounding down is conservative), about 960 GB/s memory bandwidth.
- Serving: vLLM (Docker, `--profile gpu`), which pre-allocates `gpu_memory_utilization` = 0.9 of
  VRAM, so the usable budget is 0.9 x 48 = 43.2 GB. Weights and overhead come out of that budget,
  and vLLM fills the rest with KV cache blocks.
- Overhead allowance: 2.5 GB for CUDA context, activations and runtime buffers (a 2 to 3 GB range).
- KV cache in FP16 (2 bytes per value). GB means 10^9 bytes.

### Model configuration used

Qwen2.5-7B-Instruct, read from Ollama `/api/show` model_info for the installed model:
`qwen2.block_count` 28, `qwen2.attention.head_count` 28, `qwen2.attention.head_count_kv` 4,
`qwen2.embedding_length` 3584, `qwen2.context_length` 32768, vocabulary 152,064 tokens,
`general.parameter_count` 7,615,616,512. Head dimension = 3584 / 28 = 128.

bge-m3, from the same source: `bert.block_count` 24, `bert.embedding_length` 1024,
`general.parameter_count` 566,703,104.

### VRAM for the current models

Weights = parameters x bits per parameter / 8.

| component | arithmetic | GB |
|---|---|---|
| Qwen2.5-7B, FP16 | 7,615,616,512 x 16 / 8 | 15.23 |
| Qwen2.5-7B, 4-bit (Q4_K_M at about 4.85 bits/param) | 7,615,616,512 x 4.85 / 8 | 4.62 |
| bge-m3, FP16 | 566,703,104 x 2 | 1.13 |

The installed Q4_K_M file is 4,683,073,952 bytes, an effective 4.92 bits per parameter, so 4.85 is
a slight underestimate. vLLM normally serves 4-bit models in AWQ or GPTQ format rather than GGUF
Q4_K_M; their size is similar (about 4.25 to 4.85 bits per parameter including scales).

KV cache per token = 2 (K and V) x layers x KV heads x head dimension x bytes per value:

- 2 x 28 x 4 x 128 x 2 = 57,344 bytes per token (56 KiB)
- 8,192 tokens: 57,344 x 8,192 = 469,762,048 bytes = 0.47 GB
- 32,768 tokens: 57,344 x 32,768 = 1,879,048,192 bytes = 1.88 GB

Single stream totals (LLM weights + bge-m3 + KV + 2.5 GB overhead):

| LLM precision | at 8k context | at 32k context |
|---|---|---|
| FP16 | 15.23 + 1.13 + 0.47 + 2.5 = 19.33 GB | 15.23 + 1.13 + 1.88 + 2.5 = 20.74 GB |
| 4-bit | 4.62 + 1.13 + 0.47 + 2.5 = 8.72 GB | 4.62 + 1.13 + 1.88 + 2.5 = 10.13 GB |

Both fit with wide margin. Under vLLM's pre-allocation, the KV pool for the 7B model alone is:

- FP16: 43.2 - 15.23 - 2.5 = 25.47 GB, / 57,344 bytes = about 444,000 tokens (about 13 full
  32k contexts at once).
- 4-bit: 43.2 - 4.62 - 2.5 = 36.08 GB, / 57,344 bytes = about 629,000 tokens.

vLLM serves one model per process. If bge-m3 runs on the same GPU in a second process, the LLM's
`gpu_memory_utilization` has to be lowered (for example to 0.85) to leave room for it.

### Single-stream decode speed

Decoding one token reads roughly every weight once, so single-stream decode is bandwidth bound:

tokens/s ≈ efficiency x bandwidth / bytes read per token, with bytes read per token ≈ weight bytes
and an assumed efficiency of 0.6 (0.6 x 960 = 576 GB/s effective). KV reads are ignored, which is
reasonable at short contexts.

| model | weight bytes | estimate |
|---|---|---|
| Qwen2.5-7B FP16 | 15.23 GB | 576 / 15.23 = about 38 tokens/s |
| Qwen2.5-7B 4-bit | 4.62 GB | 576 / 4.62 = about 125 tokens/s |

These are decode rates only. Prompt processing on the GPU is compute bound and would add a short,
separate cost per request. They are not directly comparable to the 9.3 tokens/s measured on the
Mac, which includes prefill (see caveats).

### Larger models in 48 GB

Configurations below are from the published Qwen2.5 `config.json` files, not read from this
machine. All three use 8 KV heads and head dimension 128.

| model | params | layers | KV bytes/token (2 x L x 8 x 128 x 2) |
|---|---|---|---|
| Qwen2.5-14B | 14,770,033,664 | 48 | 196,608 |
| Qwen2.5-32B | 32,763,876,352 | 64 | 262,144 |
| Qwen2.5-72B | 72,706,203,648 | 80 | 327,680 |

KV pool = 43.2 GB - weights - 2.5 GB overhead, then divided by KV bytes per token. Decode estimate =
576 GB/s / weight bytes.

| option | weights | KV pool | KV tokens | decode estimate | verdict |
|---|---|---|---|---|---|
| 14B FP16 | 14.77 x 2 = 29.54 GB | 11.16 GB | about 56,800 (1.7 x 32k) | about 19.5 tokens/s | fits |
| 32B 4-bit (4.85 bits) | 32.76 x 4.85 / 8 = 19.86 GB | 20.84 GB | about 79,500 (2.4 x 32k) | about 29 tokens/s | fits, best balance |
| 32B 8-bit (Q8_0, 8.5 bits) | 32.76 x 8.5 / 8 = 34.81 GB | 5.89 GB | about 22,500 (0.7 x 32k) | about 16.5 tokens/s | fits, short contexts only |
| 32B FP8 (8.0 bits) | 32.76 GB | 7.94 GB | about 30,300 (0.9 x 32k) | about 17.6 tokens/s | fits, short contexts only |
| 72B 4-bit (4.85 bits) | 72.71 x 4.85 / 8 = 44.08 GB | 43.2 - 44.08 - 2.5 < 0 | none | about 13 tokens/s | does not fit at 0.9 utilisation |
| 72B 4-bit (4.25 bits) | 72.71 x 4.25 / 8 = 38.63 GB | 2.07 GB | about 6,300 | about 15 tokens/s | borderline |

Even using the full 48 GB, a 72B model at 4.85 bits leaves 48 - 44.08 - 2.5 = 1.42 GB, about 4,300
tokens of KV cache, with no room for bge-m3. A 32B model at 4-bit is the largest option that keeps
full 32k contexts and the embedding model on the same card.

## Estimated answer time on the RTX 6000 Ada (ESTIMATES)

These figures are derived from the measured request mix above and the 4-bit decode estimate. They
are not measurements.

- Requests that called the model (16 of the 20 timed): on average 119 completion tokens and 1.94
  model calls per answer, and 0.29 s outside the model. On the laptop these 16 took 13.1 s on
  average. The slowest request (3 calls, 239 tokens, 0.36 s outside the model) took 27.5 s on the
  laptop.
- Assumed: up to 2,000 input tokens per model call, processed at 4,000 tokens/s or faster on the
  GPU (prefill is compute-bound and much faster than decode; this rate is an assumption, not
  measured). Decode at about 125 tokens/s (7B, 4-bit, from the estimate above).
- Average answer that calls the model: 1.94 x (2,000 / 4,000) s + 119 / 125 s + 0.29 s =
  0.97 + 0.95 + 0.29, about 2.2 s (laptop: 13.1 s).
- Slowest answer (the same request): 3 x 0.5 s + 239 / 125 s + 0.36 s = 1.5 + 1.91 + 0.36, about
  3.8 s (laptop: 27.5 s).
- Predictor: no model call, so its time is set by the database query and stays well under a
  second, as measured on the laptop.

## Running cost

Assumptions: electricity at ₹8 per kWh (a placeholder; replace with the actual tariff) and a
workstation with one RTX 6000 Ada drawing about 450 W under load.

- Per hour: 0.45 kW x 1 h = 0.45 kWh; 0.45 x ₹8 = ₹3.60
- Per 8-hour day: 0.45 kW x 8 h = 3.6 kWh; 3.6 x ₹8 = ₹28.80

The Mac's draw under load was not measured (that needs `powermetrics`, which requires root). One
idle reading of system power input from the battery controller (via `ioreg`), taken after the run, was
about 28.5 W, which at ₹8 per kWh is about ₹0.23 per hour. Draw during inference is higher.

## Caveats

- One machine, one run. Numbers were not re-run or averaged across runs.
- The run was disturbed. The six answer questions took 5.0 to 8.4 s at the start (three of them as
  warm-ups) and 14.3 to 16.6 s when repeated near the end, and one refusal took 3.5 s early
  and 8.3 s later. Swap use was 17.0 GB of 18.4 GB just after the run, so memory pressure on the 16 GB machine is the likely cause, though
  not proven. The p95 and mean are inflated by this; the early requests are closer to an
  undisturbed figure.
- Also running during the measurement: the Vite dev server for the web UI (idle), desktop
  applications, and a shell loop that checked the log file every 5 s. No tests, browsers under
  automation or other model servers were running.
- The generation rate includes prompt processing, so it understates decode speed. As a rough
  check (an estimate, using about 153 GB/s for the M5 and the same 0.6 factor), pure decode of
  the 4.68 GB model would be about 0.6 x 153 / 4.68 = 20 tokens/s.
- Model output length varies with wording and question, so per-request latency varies even at a
  fixed hardware speed. The golden questions are a small, specific mix (answers, refusals,
  injection and adversarial cases), not a sample of real traffic.
- All GPU figures are ESTIMATES from arithmetic, not measurements.
