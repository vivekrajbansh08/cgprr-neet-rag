"""Benchmark the running stack: /ask end-to-end + LLM share, embedding throughput, /predict latency.

Usage: uv run python -m neet_bench [--n 20] [--warmup 3] [--embed-k 64] [--embed-batch 64]
       [--predict-n 50] [--predict-warmup 3] [--skip ask,embed,predict]   (or: make bench, after make serve)

Questions come from the locked golden set (the file named in eval/golden/LOCK.json; the lock is
verified first). /ask gets every question except predictor questions with expected_behavior answer;
those go to /predict with their locked `inputs`. Requests are sequential. Output: JSON in
eval/results/bench/<UTC ts>.json (gitignored) and a markdown summary on stdout. Neither holds an
MCC figure: answers, predictor options and chunk texts are discarded after timing.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import psycopg
import yaml
from neet_common.config import REPO_ROOT, Settings
from neet_common.db import connect
from neet_ingest.embed import EmbeddingError, embed_batches

from neet_bench.env import capture
from neet_bench.phases import CHUNK_SQL, run_ask, run_embed, run_predict
from neet_bench.report import markdown
from neet_bench.stats import PERCENTILE_METHOD

LOCK = REPO_ROOT / "eval" / "golden" / "LOCK.json"
OUT_DIR = REPO_ROOT / "eval" / "results" / "bench"
PHASES = ("ask", "embed", "predict")


def golden_lock_problems(root: Path) -> list[str]:
    spec = importlib.util.spec_from_file_location(
        "check_golden_lock", root / "scripts" / "check_golden_lock.py"
    )
    if spec is None or spec.loader is None:
        return ["scripts/check_golden_lock.py not found"]
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return list(mod.check(root))


def uses_predictor(q: dict[str, Any]) -> bool:
    return q["category"] == "predictor" and q["expected_behavior"] == "answer" and "inputs" in q


def split_questions(
    questions: list[dict[str, Any]],
) -> tuple[list[tuple[str, str]], list[tuple[str, dict[str, Any]]]]:
    ask = [(q["id"], q["question"]) for q in questions if not uses_predictor(q)]
    pred = [(q["id"], q["inputs"]) for q in questions if uses_predictor(q)]
    return ask, pred


def chunk_texts(settings: Settings, k: int) -> list[str]:
    with connect(settings, "neet_reader") as conn:
        return [r[0] for r in conn.execute(CHUNK_SQL, (k,)).fetchall()]


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--answer-url", default=None, help="default: ANSWER_URL setting")
    ap.add_argument("--predictor-url", default=None, help="default: PREDICTOR_URL setting")
    ap.add_argument("--n", type=int, default=20, help="timed /ask requests (questions cycled)")
    ap.add_argument("--warmup", type=int, default=3, help="discarded /ask warm-up requests")
    ap.add_argument("--embed-k", type=int, default=64, help="chunk texts to embed")
    ap.add_argument("--embed-batch", type=int, default=64, help="texts per request (index uses 64)")
    ap.add_argument("--predict-n", type=int, default=50, help="timed /predict requests")
    ap.add_argument("--predict-warmup", type=int, default=3, help="discarded /predict warm-ups")
    ap.add_argument("--skip", default="", help="comma list of phases to skip: ask,embed,predict")
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = ap.parse_args(argv)
    args.skip = {s.strip() for s in args.skip.split(",") if s.strip()}
    if bad := args.skip - set(PHASES):
        ap.error(f"unknown phase(s) in --skip: {sorted(bad)}")
    if (
        min(args.n, args.predict_n, args.embed_k, args.embed_batch) < 1
        or min(args.warmup, args.predict_warmup) < 0
    ):
        ap.error("counts must be >= 1 and warm-ups >= 0")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = Settings()
    problems = golden_lock_problems(REPO_ROOT)
    if problems:
        print("GOLDEN LOCK BROKEN; refusing to run:", *problems, sep="\n  ", file=sys.stderr)
        return 1
    golden_file = json.loads(LOCK.read_text(encoding="utf-8"))["file"]
    data = yaml.safe_load((REPO_ROOT / golden_file).read_text(encoding="utf-8"))
    ask_qs, pred_qs = split_questions(data["questions"])

    started = datetime.now(UTC)
    result: dict[str, Any] = {
        "started_utc": started.isoformat(timespec="seconds"),
        "golden_file": golden_file,
        "percentile_method": PERCENTILE_METHOD,
        "settings": {
            "llm_model": settings.llm_model,
            "embed_model": settings.embed_model,
            "llm_base_url": settings.llm_base_url,
        },
        "args": {
            k: (sorted(v) if isinstance(v, set) else str(v) if isinstance(v, Path) else v)
            for k, v in vars(args).items()
        },
    }
    with httpx.Client(timeout=600.0) as client:
        result["environment"] = capture(
            client, settings.llm_base_url, [settings.llm_model, settings.embed_model], str(REPO_ROOT)
        )
        if "ask" not in args.skip:
            url = args.answer_url or settings.answer_url
            result["ask"] = run_ask(client, url, ask_qs, args.n, args.warmup)
        if "embed" not in args.skip:
            try:
                texts = chunk_texts(settings, args.embed_k)
                result["embed"] = run_embed(client, settings, texts, args.embed_batch, embed_batches)
            except (psycopg.Error, httpx.HTTPError, EmbeddingError, KeyError, ValueError) as exc:
                result["embed"] = {"error": f"{type(exc).__name__}: {exc}"}
        if "predict" not in args.skip:
            url = args.predictor_url or settings.predictor_url
            result["predict"] = run_predict(client, url, pred_qs, args.predict_n, args.predict_warmup)
    result["finished_utc"] = datetime.now(UTC).isoformat(timespec="seconds")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out = args.out_dir / f"{started.strftime('%Y%m%dT%H%M%SZ')}.json"
    out.write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")
    print(markdown(result))
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
