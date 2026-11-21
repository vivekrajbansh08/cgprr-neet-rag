"""Run the locked eval set against the answer service and write eval/results/score_table.md.

Usage: uv run python -m neet_eval [--answer-url URL]   (or: make eval, after make serve)

The golden lock is verified first (scripts/check_golden_lock.py); a broken lock aborts the run.
Predictor questions are reported as "pending: Step 5". The committed score table holds pass/fail
and check names only (no MCC figures); raw answers go to eval/results/runs/<timestamp>.jsonl
(gitignored).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import yaml
from neet_common.config import REPO_ROOT, Settings

from neet_eval.checks import check_question

LOCK = REPO_ROOT / "eval" / "golden" / "LOCK.json"
SYSTEM_PROMPT = REPO_ROOT / "services" / "answer" / "prompts" / "system.txt"
RESULTS = REPO_ROOT / "eval" / "results"


def golden_lock_problems(root: Path) -> list[str]:
    spec = importlib.util.spec_from_file_location(
        "check_golden_lock", root / "scripts" / "check_golden_lock.py"
    )
    if spec is None or spec.loader is None:
        return ["scripts/check_golden_lock.py not found"]
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return list(mod.check(root))


def ask(client: httpx.Client, url: str, question: str) -> tuple[dict[str, Any], float]:
    t0 = time.perf_counter()
    resp = client.post(url.rstrip("/") + "/ask", json={"question": question, "debug": True})
    resp.raise_for_status()
    return resp.json(), time.perf_counter() - t0


def score_table(rows: list[dict[str, Any]], meta: dict[str, Any]) -> str:
    lines = [
        "# Eval score table",
        "",
        "Source: Medical Counselling Committee (MCC), Government of India, mcc.nic.in",
        "",
        f"- Run: {meta['run_at']} (UTC), model `{meta['model']}`, golden set `{meta['golden']}`",
        "- The golden set is also the dev set: changes made after seeing failures are logged in"
        " `docs/eval_log.md`, so this is not a held-out score.",
        "- Pass/fail and check names only; no MCC figures. Raw answers: `eval/results/runs/` (gitignored).",
        "",
        "| id | category | result | failed checks | latency (s) |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        lat = "" if r["latency_s"] is None else f"{r['latency_s']:.1f}"
        lines.append(f"| {r['id']} | {r['category']} | {r['result']} | {', '.join(r['failed'])} | {lat} |")
    lines += ["", "| category | passed | scored | pending |", "|---|---|---|---|"]
    cats = dict.fromkeys(r["category"] for r in rows)
    for cat in cats:
        cr = [r for r in rows if r["category"] == cat]
        scored = [r for r in cr if r["result"] in ("pass", "fail")]
        lines.append(
            f"| {cat} | {sum(r['result'] == 'pass' for r in scored)} | {len(scored)} |"
            f" {sum(r['result'].startswith('pending') for r in cr)} |"
        )
    scored = [r for r in rows if r["result"] in ("pass", "fail")]
    lines += [
        "",
        f"Total: {sum(r['result'] == 'pass' for r in scored)} / {len(scored)} scored questions passed;"
        f" {len(rows) - len(scored)} pending.",
        f"Median latency: {meta['median_latency_s']:.1f} s. Generation speed: {meta['tokens_per_s']:.1f}"
        " tokens/s (completion tokens / LLM seconds, all calls).",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Score the locked golden set against /ask")
    ap.add_argument("--answer-url", default=None)
    args = ap.parse_args(argv)
    settings = Settings()
    url = args.answer_url or settings.answer_url

    problems = golden_lock_problems(REPO_ROOT)
    if problems:
        print("GOLDEN LOCK BROKEN; refusing to run the eval:", *problems, sep="\n  ", file=sys.stderr)
        return 1
    golden_file = json.loads(LOCK.read_text(encoding="utf-8"))["file"]  # the file the lock pins
    data = yaml.safe_load((REPO_ROOT / golden_file).read_text(encoding="utf-8"))
    prompt_text = SYSTEM_PROMPT.read_text(encoding="utf-8")

    run_at = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    runs_dir = RESULTS / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    raw_path = runs_dir / f"{run_at}.jsonl"
    rows: list[dict[str, Any]] = []
    tokens = 0
    llm_seconds = 0.0
    with httpx.Client(timeout=600.0) as client, raw_path.open("w", encoding="utf-8") as raw:
        for q in data["questions"]:
            if q["category"] == "predictor":
                rows.append(
                    {"id": q["id"], "category": q["category"], "result": "pending: Step 5", "failed": [],
                     "latency_s": None}
                )  # fmt: skip
                continue
            try:
                resp, latency = ask(client, url, q["question"])
            except httpx.HTTPError as exc:
                print(f"answer service unreachable at {url}: {exc} (run `make serve`)", file=sys.stderr)
                return 2
            result = check_question(q, resp, REPO_ROOT, prompt_text)
            for call in resp.get("debug", {}).get("llm_calls") or []:
                tokens += call.get("completion_tokens") or 0
                llm_seconds += call.get("seconds") or 0.0
            rows.append(
                {
                    "id": q["id"],
                    "category": q["category"],
                    "result": "pass" if result.passed else "fail",
                    "failed": result.failed,
                    "latency_s": latency,
                }
            )
            raw.write(json.dumps({"id": q["id"], "latency_s": latency, "checks": result.model_dump(),
                                  "response": resp}, default=str) + "\n")  # fmt: skip
            print(f"{q['id']:8} {'pass' if result.passed else 'FAIL'} {', '.join(result.failed)}")

    latencies = [r["latency_s"] for r in rows if r["latency_s"] is not None]
    meta = {
        "run_at": run_at,
        "model": settings.llm_model,
        "golden": golden_file,
        "median_latency_s": statistics.median(latencies) if latencies else 0.0,
        "tokens_per_s": tokens / llm_seconds if llm_seconds else 0.0,
    }
    (RESULTS / "score_table.md").write_text(score_table(rows, meta), encoding="utf-8")
    print(f"wrote {RESULTS / 'score_table.md'} and {raw_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
