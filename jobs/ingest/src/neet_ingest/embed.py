"""Embeddings from the local OpenAI-compatible endpoint (LLM_BASE_URL/embeddings). No cloud calls."""

from __future__ import annotations

import httpx
from neet_common.config import Settings

COLUMN_DIM = 1024  # neet.chunk.embedding is vector(1024) (db/migrations/003_core.sql)


class EmbeddingError(RuntimeError):
    """The embedding endpoint returned something unexpected, or EMBED_DIM does not fit the column."""


def embed_batches(
    client: httpx.Client, settings: Settings, texts: list[str], batch: int = 64
) -> list[list[float]]:
    if settings.embed_dim != COLUMN_DIM:
        raise EmbeddingError(
            f"EMBED_DIM={settings.embed_dim} but neet.chunk.embedding is vector({COLUMN_DIM});"
            " a different embedding size needs a new migration"
        )
    out: list[list[float]] = []
    url = settings.llm_base_url.rstrip("/") + "/embeddings"
    headers = {"Authorization": f"Bearer {settings.llm_api_key.get_secret_value()}"}
    for i in range(0, len(texts), batch):
        part = texts[i : i + batch]
        resp = client.post(url, json={"model": settings.embed_model, "input": part}, headers=headers)
        resp.raise_for_status()
        data = sorted(resp.json()["data"], key=lambda d: d["index"])
        indexes = [d["index"] for d in data]
        if indexes != list(range(len(part))):
            raise EmbeddingError(f"asked for {len(part)} embeddings, got indexes {indexes}")
        for d in data:
            if len(d["embedding"]) != settings.embed_dim:
                raise EmbeddingError(f"embedding dim {len(d['embedding'])} != EMBED_DIM {settings.embed_dim}")
            out.append(d["embedding"])
    return out
