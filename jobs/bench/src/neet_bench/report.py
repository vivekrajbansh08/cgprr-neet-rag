"""Markdown summary of a bench result dict (timings and environment only; no MCC figures)."""

from __future__ import annotations

from typing import Any


def _f(v: float | None, fmt: str = ".2f", suffix: str = "") -> str:
    return "n/a" if v is None else f"{v:{fmt}}{suffix}"


def _row(*cells: object) -> str:
    return "| " + " | ".join(str(c) for c in cells) + " |"


def markdown(r: dict[str, Any]) -> str:
    env = r.get("environment") or {}
    hw = env.get("hardware") or {}
    git = env.get("git") or {}
    os_line = " ".join(
        line.split(":", 1)[-1].strip() for line in (hw.get("os") or "").splitlines() if line.strip()
    )
    lines = [
        "# Bench summary",
        "",
        f"- Run: {r['started_utc']} to {r.get('finished_utc')} (UTC); golden set `{r['golden_file']}`",
        f"- Git: `{git.get('commit')}`{' (dirty)' if git.get('dirty') else ''}",
        f"- Hardware: {hw.get('cpu')}, {hw.get('memory_gib')} GiB; OS: {os_line or 'n/a'}"
        + (f"; GPU: {hw['gpu']}" if hw.get("gpu") else ""),
        f"- Runtime: {env.get('ollama_cli_version') or 'n/a'} (API {env.get('ollama_api_version')}),"
        f" endpoint `{env.get('llm_base_url')}`; loaded at start: {env.get('ollama_loaded_models_at_start')}",
        f"- Percentiles: {r['percentile_method']}",
        "",
        "| model | digest | params | quant | context | licence |",
        "|---|---|---|---|---|---|",
    ]
    for m in env.get("models") or []:
        digest = (m.get("digest") or "")[:12] or "n/a"
        lines.append(
            f"| {m['name']} | {digest} | {m.get('parameter_size')} ({m.get('parameter_count')}) |"
            f" {m.get('quantization_level')} | {m.get('context_length')} | {m.get('licence_line')} |"
        )
    if "ask" in r:
        s = r["ask"]["summary"]
        share = s["llm_time_share"]
        lines += [
            "",
            f"## /ask ({s['requests']} timed, {r['ask']['warmup']} warm-up discarded, sequential)",
            "",
            "| p50 e2e | p95 e2e | mean e2e | LLM time share | gen tokens/s | LLM calls | errors | status |",
            "|---|---|---|---|---|---|---|---|",
            _row(
                _f(s["p50_s"], suffix=" s"),
                _f(s["p95_s"], suffix=" s"),
                _f(s["mean_s"], suffix=" s"),
                _f(None if share is None else share * 100, ".1f", "%"),
                _f(s["gen_tokens_per_s"], ".1f"),
                s["llm_calls"],
                s["errors"],
                ", ".join(f"{k}: {v}" for k, v in s["status_counts"].items()),
            ),
            "",
            "LLM time share = sum LLM s / sum e2e s; gen tokens/s = sum completion tokens / sum LLM s"
            " (from /ask debug.llm_calls, same accounting as jobs/eval).",
        ]
    if "embed" in r:
        e = r["embed"]
        lines += ["", "## Embeddings", ""]
        if "error" in e:
            lines.append(f"Error: {e['error']}")
        else:
            lines += [
                "| model | chunks | batch size | batches | seconds | chunks/s | warm-up batch |",
                "|---|---|---|---|---|---|---|",
                f"| {e['model']} | {e['chunks']} | {e['batch_size']} | {e['batches']} | {_f(e['seconds'])} |"
                f" {_f(e['chunks_per_s'], '.1f')} | {_f(e['warmup_batch_s'], suffix=' s')} |",
            ]
    if "predict" in r:
        s = r["predict"]["summary"]
        lines += [
            "",
            f"## /predict ({s['requests']} timed, {r['predict']['warmup']} warm-up discarded, sequential)",
            "",
            "| p50 | p95 | mean | errors |",
            "|---|---|---|---|",
            _row(
                _f(s["p50_s"], ".3f", " s"),
                _f(s["p95_s"], ".3f", " s"),
                _f(s["mean_s"], ".3f", " s"),
                s["errors"],
            ),
        ]
    return "\n".join(lines)
