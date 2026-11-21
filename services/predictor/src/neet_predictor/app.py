"""FastAPI entry point for the predictor service (port 8003). Connects as neet_reader only.

Options are computed by fixed SQL plus the pure rule in neet_predictor.rule. No LLM is involved:
explanations are built deterministically from the rows. The pool is built in the lifespan and kept
on app.state (no module-level singletons); it opens lazily so the service starts if Postgres is down.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

import psycopg
from fastapi import Depends, FastAPI, HTTPException, Request
from neet_common.config import Settings
from neet_common.db import reader_pool
from neet_common.predictor import CANDIDATE_CATEGORIES, FormOptions, PredictRequest, PredictResponse
from psycopg_pool import ConnectionPool, PoolTimeout

from neet_predictor import rule, sql

log = logging.getLogger("neet_predictor")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    pool = reader_pool(Settings())
    pool.open(wait=False)
    app.state.pool = pool
    try:
        yield
    finally:
        pool.close()


app = FastAPI(title="neet-predictor", lifespan=lifespan)


def get_pool(request: Request) -> ConnectionPool:
    pool = getattr(request.app.state, "pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="service not initialised")
    return pool


PoolDep = Annotated[ConnectionPool, Depends(get_pool)]


def get_form_values(request: Request, pool: PoolDep) -> FormOptions:
    """Distinct quotas / courses / states from the DB, loaded once per process and kept on app.state."""
    cached = getattr(request.app.state, "form_values", None)
    if cached is None:
        try:
            quotas, courses, states = sql.form_values(pool)
        except (psycopg.Error, PoolTimeout) as exc:
            raise _db_error(exc) from exc
        cached = FormOptions(
            categories=list(CANDIDATE_CATEGORIES),
            quotas=quotas,
            courses=courses,
            rounds=[1, 2, 3],
            states=states,
        )
        request.app.state.form_values = cached
    return cached


FormDep = Annotated[FormOptions, Depends(get_form_values)]


def unknown_inputs(req: PredictRequest, form: FormOptions) -> list[dict[str, str]]:
    """Inputs that are not exact DB values. Answering for them would state a false 'no institute'."""
    bad = []
    if req.quota not in form.quotas:
        bad.append(("quota", req.quota))
    if req.course not in form.courses:
        bad.append(("course", req.course))
    if req.state is not None and req.state not in form.states:
        bad.append(("state", req.state))
    return [
        {"loc": f"body.{field}", "msg": f"unknown {field} {value!r}; use a value from GET /form_options"}
        for field, value in bad
    ]


def _db_error(exc: Exception) -> HTTPException:
    log.error("database error: %s", type(exc).__name__)
    return HTTPException(status_code=503, detail=f"database unavailable: {type(exc).__name__}")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "predictor"}


@app.get("/health")
def health(request: Request) -> dict[str, str]:
    pool = getattr(request.app.state, "pool", None)
    db = "unknown"
    if pool is not None:
        try:
            with pool.connection(timeout=3) as conn:
                conn.execute("SELECT 1")
            db = "ok"
        except (psycopg.Error, PoolTimeout):
            db = "down"
    return {"status": "ok", "service": "predictor", "db": db}


@app.post("/predict")
def predict(req: PredictRequest, pool: PoolDep, form: FormDep) -> PredictResponse:
    if errors := unknown_inputs(req, form):
        raise HTTPException(status_code=422, detail=errors)
    cats = rule.eligible_categories(req.category, req.pwd)
    try:
        rows = sql.fetch_rows(pool, round_=req.round, quota=req.quota, course=req.course, cats=cats)
    except (psycopg.Error, PoolTimeout) as exc:
        raise _db_error(exc) from exc
    return rule.predict(rows, req)


@app.get("/form_options")
def form_options(form: FormDep) -> FormOptions:
    return form
