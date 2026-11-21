"""FastAPI entry point for the answer service (port 8002).

Calls retrieval over HTTP (RETRIEVAL_URL) and the local LLM (LLM_BASE_URL). Clients are built in the
lifespan and kept on app.state; no module-level singletons. Every /ask is logged to logs/answer.log.
"""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from neet_common.config import REPO_ROOT, Settings
from neet_common.llm import LLMClient, is_local_endpoint
from neet_common.schemas import AskRequest, AskResponse

from neet_answer.pipeline import Pipeline
from neet_answer.reqlog import RequestLog
from neet_answer.retrieval_client import HttpRetrieval

log = logging.getLogger("neet_answer")

SYSTEM_PROMPT = REPO_ROOT / "services" / "answer" / "prompts" / "system.txt"
LOG_PATH = REPO_ROOT / "logs" / "answer.log"


@dataclass
class Deps:
    pipeline: Pipeline
    reqlog: RequestLog
    retrieval_url: str
    model: str
    closers: list[httpx.Client]


def build_deps(settings: Settings, *, log_path: Path = LOG_PATH) -> Deps:
    if not is_local_endpoint(settings.llm_base_url):
        log.warning("LLM_BASE_URL host is not loopback/private: only a local endpoint is allowed (rule c)")
    llm_http = httpx.Client(timeout=settings.llm_timeout_s)
    ret_http = httpx.Client(timeout=30.0)
    pipeline = Pipeline(
        llm=LLMClient(settings, llm_http),
        retrieval=HttpRetrieval(settings.retrieval_url, ret_http),
        system_prompt=SYSTEM_PROMPT.read_text(encoding="utf-8"),
    )
    return Deps(
        pipeline=pipeline,
        reqlog=RequestLog(log_path),
        retrieval_url=settings.retrieval_url,
        model=settings.llm_model,
        closers=[llm_http, ret_http],
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    deps = build_deps(Settings())
    app.state.deps = deps
    try:
        yield
    finally:
        for c in deps.closers:
            c.close()


app = FastAPI(title="neet-answer", lifespan=lifespan)


def get_deps(request: Request) -> Deps:
    deps = getattr(request.app.state, "deps", None)
    if deps is None:
        raise HTTPException(status_code=503, detail="service not initialised")
    return deps


DepsDep = Annotated["Deps", Depends(get_deps)]


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "answer"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "answer"}


@app.post("/ask")
def ask(req: AskRequest, deps: DepsDep) -> AskResponse:
    t0 = time.perf_counter()
    resp = deps.pipeline.ask(req.question)
    latency = round(time.perf_counter() - t0, 3)
    resp.debug.latency_s = latency
    resp.debug.model = deps.model
    tokens = sum(int(c.get("completion_tokens") or 0) for c in resp.debug.llm_calls)
    verifier = resp.debug.verifier or {}
    deps.reqlog.write(
        {
            "question": req.question,
            "status": resp.status,
            "slots": resp.debug.slots,
            "sources": [s.cell.id for s in resp.sources],
            "cited": [c.sid for c in resp.citations],
            "verifier_ok": verifier.get("ok"),
            "verifier_errors": verifier.get("errors"),
            "template": resp.debug.template,
            "latency_s": latency,
            "completion_tokens": tokens,
            "trace": resp.debug.trace,  # failed drafts and raw LLM slots: log only, unless debug=true
        }
    )
    if not req.debug:
        resp.debug.trace = None
    return resp
