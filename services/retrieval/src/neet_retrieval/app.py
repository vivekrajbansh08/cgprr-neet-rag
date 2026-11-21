"""FastAPI entry point for the retrieval service (port 8001). Connects as neet_reader only.

Clients and the connection pool are built in the lifespan and kept on app.state (no module-level
singletons). The institute catalog is loaded lazily so the service starts even if Postgres is down.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Annotated

import httpx
import psycopg
from fastapi import Depends, FastAPI, HTTPException, Request
from neet_common.config import Settings
from neet_common.db import reader_pool
from neet_common.llm import LLMClient
from neet_common.schemas import (
    CellsRequest,
    CellsResponse,
    InstituteNames,
    ResolveRequest,
    ResolveResponse,
    SearchRequest,
    SearchResponse,
)
from psycopg_pool import ConnectionPool, PoolTimeout

from neet_retrieval import core

log = logging.getLogger("neet_retrieval")


@dataclass
class Deps:
    pool: ConnectionPool
    llm: LLMClient | None
    http: httpx.Client
    catalog: core.Catalog | None = field(default=None)

    def get_catalog(self) -> core.Catalog:
        if self.catalog is None:
            self.catalog = core.load_catalog(self.pool)
        return self.catalog


def build_deps(settings: Settings) -> Deps:
    pool = reader_pool(settings)
    pool.open(wait=False)
    http = httpx.Client(timeout=30.0)
    llm = LLMClient(settings, http) if settings.embed_model else None
    return Deps(pool=pool, llm=llm, http=http)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    deps = build_deps(Settings())
    app.state.deps = deps
    try:
        yield
    finally:
        deps.pool.close()
        deps.http.close()


app = FastAPI(title="neet-retrieval", lifespan=lifespan)


def get_deps(request: Request) -> Deps:
    deps = getattr(request.app.state, "deps", None)
    if deps is None:
        raise HTTPException(status_code=503, detail="service not initialised")
    return deps


DepsDep = Annotated["Deps", Depends(get_deps)]


def _db_errors(exc: Exception) -> HTTPException:
    log.error("database error: %s", type(exc).__name__)
    return HTTPException(status_code=503, detail=f"database unavailable: {type(exc).__name__}")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "retrieval"}


@app.get("/health")
def health(request: Request) -> dict[str, str]:
    deps = getattr(request.app.state, "deps", None)
    db = "unknown"
    if deps is not None:
        try:
            with deps.pool.connection(timeout=3) as conn:
                conn.execute("SELECT 1")
            db = "ok"
        except (psycopg.Error, PoolTimeout):
            db = "down"
    return {"status": "ok", "service": "retrieval", "db": db}


@app.post("/resolve_institute")
def resolve_institute(req: ResolveRequest, deps: DepsDep) -> ResolveResponse:
    try:
        return core.resolve_institute(deps.pool, deps.llm, deps.get_catalog(), req)
    except (psycopg.Error, PoolTimeout) as exc:
        raise _db_errors(exc) from exc


@app.get("/institute_names")
def institute_names(deps: DepsDep) -> InstituteNames:
    try:
        cat = deps.get_catalog()
    except (psycopg.Error, PoolTimeout) as exc:
        raise _db_errors(exc) from exc
    return InstituteNames(
        names=sorted({i.display_name.split(",", 1)[0].strip() for i in cat.institutes.values()})
    )


@app.post("/cells")
def cells(req: CellsRequest, deps: DepsDep) -> CellsResponse:
    try:
        return core.get_cells(deps.pool, req)
    except (psycopg.Error, PoolTimeout) as exc:
        raise _db_errors(exc) from exc


@app.post("/search")
def search(req: SearchRequest, deps: DepsDep) -> SearchResponse:
    try:
        return core.search(deps.pool, deps.llm, req)
    except (psycopg.Error, PoolTimeout) as exc:
        raise _db_errors(exc) from exc
