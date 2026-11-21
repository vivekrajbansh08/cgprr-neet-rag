"""Unit tests for neet_bench: percentile maths, /ask aggregation, phases over fake HTTP. No network."""

from __future__ import annotations

import json
from itertools import count

import httpx
import pytest
from neet_bench.__main__ import parse_args, split_questions
from neet_bench.env import model_info, native_base
from neet_bench.phases import run_ask, run_embed, run_predict
from neet_bench.report import markdown
from neet_bench.stats import ask_summary, cycle, llm_usage, percentile
from neet_common.config import Settings

CALL = {"seconds": 0.5, "completion_tokens": 20}


def rec(status: str, e2e: float, llm: float, tokens: int, calls: int) -> dict:
    return {"ok": True, "status": status, "e2e_s": e2e, "llm_s": llm, "completion_tokens": tokens,
            "llm_calls": calls}  # fmt: skip


def fake_clock(step: float = 1.0):
    c = count()
    return lambda: next(c) * step


# --- percentile ---------------------------------------------------------------------------------


def test_percentile_linear_interpolation():
    xs = [1.0, 2.0, 3.0, 4.0]
    assert percentile(xs, 50) == pytest.approx(2.5)
    assert percentile(xs, 95) == pytest.approx(3.85)  # pos 2.85 -> 3 + 0.85
    assert percentile(xs, 0) == 1.0
    assert percentile(xs, 100) == 4.0


def test_percentile_unsorted_single_and_empty():
    assert percentile([5.0, 1.0, 3.0], 50) == 3.0
    assert percentile([7.0], 95) == 7.0
    assert percentile([], 50) is None
    with pytest.raises(ValueError):
        percentile([1.0], 101)


def test_percentile_twenty_values_p95():
    xs = [float(i) for i in range(1, 21)]  # 1..20
    assert percentile(xs, 95) == pytest.approx(19.05)  # pos 18.05
    assert percentile(xs, 50) == pytest.approx(10.5)


# --- aggregation --------------------------------------------------------------------------------


def test_llm_usage_sums_calls_and_tolerates_missing():
    resp = {"debug": {"llm_calls": [{"seconds": 1.5, "completion_tokens": 30},
                                    {"seconds": None, "completion_tokens": None},
                                    {"seconds": 0.5, "completion_tokens": 10}]}}  # fmt: skip
    assert llm_usage(resp) == (2.0, 40, 3)
    assert llm_usage({"status": "refused"}) == (0.0, 0, 0)


def test_ask_summary_share_and_tokens_are_ratios_of_sums():
    recs = [
        rec("answered", 2.0, 1.0, 50, 1),
        rec("refused", 8.0, 4.0, 50, 2),
        {"ok": False, "status": "error:ConnectError", "e2e_s": 0.1, "llm_s": 0.0,
         "completion_tokens": 0, "llm_calls": 0},
    ]  # fmt: skip
    s = ask_summary(recs)
    assert s["requests"] == 3 and s["errors"] == 1
    assert s["llm_time_share"] == pytest.approx(5.0 / 10.0)
    assert s["gen_tokens_per_s"] == pytest.approx(100 / 5.0)  # not the mean of 50/s and 12.5/s
    assert s["status_counts"] == {"answered": 1, "error:ConnectError": 1, "refused": 1}
    assert s["p50_s"] == pytest.approx(5.0)
    assert s["llm_calls"] == 3


def test_ask_summary_no_llm_time():
    s = ask_summary([{"ok": True, "status": "refused", "e2e_s": 0.2, "llm_s": 0.0,
                      "completion_tokens": 0, "llm_calls": 0}])  # fmt: skip
    assert s["gen_tokens_per_s"] is None and s["llm_time_share"] == 0.0


def test_cycle():
    assert cycle(["a", "b", "c"], 7) == ["a", "b", "c", "a", "b", "c", "a"]
    assert cycle(["a"], 0) == []
    with pytest.raises(ValueError):
        cycle([], 1)


# --- question split -----------------------------------------------------------------------------


def test_split_questions_sends_predictor_answers_to_predict():
    qs = [
        {"id": "ans-01", "category": "answerable", "expected_behavior": "answer", "question": "q1"},
        {"id": "pred-01", "category": "predictor", "expected_behavior": "answer", "question": "q2",
         "inputs": {"rank": 1}},
        {"id": "pred-04", "category": "predictor", "expected_behavior": "refuse", "question": "q3"},
    ]  # fmt: skip
    ask, pred = split_questions(qs)
    assert [a[0] for a in ask] == ["ans-01", "pred-04"]
    assert pred == [("pred-01", {"rank": 1})]


def test_parse_args_rejects_unknown_skip():
    assert parse_args(["--skip", "embed"]).skip == {"embed"}
    with pytest.raises(SystemExit):
        parse_args(["--skip", "nope"])


# --- phases over fake HTTP ----------------------------------------------------------------------


def test_run_ask_discards_warmups_and_reads_debug():
    seen: list[dict] = []

    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        seen.append(body)
        return httpx.Response(200, json={"status": "answered", "answer": "SECRET 12345",
                                         "debug": {"llm_calls": [CALL]}})  # fmt: skip

    client = httpx.Client(transport=httpx.MockTransport(handler))
    out = run_ask(client, "http://x", [("a", "qa"), ("b", "qb")], n=3, warmup=2,
                  clock=fake_clock(1.0), log=lambda _m: None)  # fmt: skip
    assert len(seen) == 5 and all(b["debug"] is True for b in seen)
    assert [r["id"] for r in out["per_request"]] == ["a", "b", "a"]  # cycle continues after warm-ups
    s = out["summary"]
    assert s["requests"] == 3 and s["p50_s"] == 1.0
    assert s["gen_tokens_per_s"] == pytest.approx(60 / 1.5)
    assert "12345" not in json.dumps(out)  # answer text is never kept


def test_run_ask_records_http_errors():
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    out = run_ask(client, "http://x", [("a", "qa")], n=2, warmup=0, clock=fake_clock(), log=lambda _m: None)
    assert out["summary"]["errors"] == 2
    assert out["summary"]["status_counts"] == {"error:HTTPStatusError": 2}


def test_run_predict_counts_and_hides_body():
    calls = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(json.loads(req.content))
        return httpx.Response(200, json={"options": [{"closing_rank": 99999}]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    out = run_predict(client, "http://x", [("p1", {"rank": 1}), ("p2", {"rank": 2})], n=4, warmup=3,
                      clock=fake_clock(0.5))  # fmt: skip
    assert len(calls) == 7
    assert out["summary"]["n"] == 4 and out["summary"]["p50_s"] == 0.5
    assert "99999" not in json.dumps(out)


def test_run_embed_warmup_then_timed():
    batches: list[int] = []

    def fake_embed(_c: httpx.Client, _s: Settings, texts: list[str], batch: int) -> list[list[float]]:
        batches.append(len(texts))
        return [[0.0] * 4 for _ in texts]

    settings = Settings(embed_model="m")
    out = run_embed(httpx.Client(), settings, ["t"] * 10, 4, fake_embed, clock=fake_clock(2.0))
    assert batches == [4, 10]  # one warm-up batch, then the full set
    assert out["batches"] == 3 and out["batch_size"] == 4
    assert out["chunks_per_s"] == pytest.approx(10 / 2.0)
    assert run_embed(httpx.Client(), settings, [], 4, fake_embed).get("error")


# --- environment and report ---------------------------------------------------------------------


def test_model_info_from_fake_ollama():
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "bge-m3:latest", "digest": "abc123",
                                                         "size": 10}]})  # fmt: skip
        return httpx.Response(200, json={
            "license": "\n\nMIT License\n\nCopyright...",
            "details": {"format": "gguf", "family": "bert", "parameter_size": "566.70M",
                        "quantization_level": "F16"},
            "model_info": {"bert.context_length": 8192, "general.parameter_count": 566703104},
        })  # fmt: skip

    client = httpx.Client(transport=httpx.MockTransport(handler))
    m = model_info(client, "http://o", "bge-m3")
    assert m["digest"] == "abc123" and m["quantization_level"] == "F16"
    assert m["context_length"] == 8192 and m["parameter_count"] == 566703104
    assert m["licence_line"] == "MIT License"


def test_native_base():
    assert native_base("http://localhost:11434/v1/") == "http://localhost:11434"
    assert native_base("http://h:8000") == "http://h:8000"


def test_markdown_renders_all_phases():
    rec = {
        "ok": True,
        "status": "answered",
        "e2e_s": 2.0,
        "llm_s": 1.0,
        "completion_tokens": 10,
        "llm_calls": 1,
    }
    r = {
        "started_utc": "t0", "finished_utc": "t1", "golden_file": "g.yaml", "percentile_method": "linear",
        "environment": {"hardware": {"cpu": "cpu", "memory_gib": 16.0, "os": "ProductName: macOS"},
                        "git": {"commit": "c"}, "models": [{"name": "m", "digest": "d"}]},
        "ask": {"warmup": 0, "summary": ask_summary([rec])},
        "embed": {"error": "no chunks"},
        "predict": {"warmup": 0, "summary": {"requests": 1, "errors": 0, "p50_s": 0.01, "p95_s": 0.01,
                                             "mean_s": 0.01}},
    }  # fmt: skip
    md = markdown(r)
    assert "## /ask" in md and "50.0%" in md and "10.0" in md and "## /predict" in md and "no chunks" in md
