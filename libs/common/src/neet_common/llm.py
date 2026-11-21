"""Minimal client for the local OpenAI-compatible endpoint (LLM_BASE_URL). No cloud LLM, no SDK.

The httpx.Client is injected so tests can pass one built on httpx.MockTransport (no network).
"""

from __future__ import annotations

import ipaddress
import time
from typing import Any
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel

from neet_common.config import Settings


def is_local_endpoint(url: str) -> bool:
    """True when the URL's host is loopback / private / link-local or 'localhost' (no cloud LLM)."""
    host = urlparse(url).hostname or ""
    if host == "localhost" or host.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private or ip.is_link_local


class LLMError(RuntimeError):
    """The endpoint was unreachable or returned something unexpected."""


class ChatResult(BaseModel):
    content: str
    completion_tokens: int | None = None
    prompt_tokens: int | None = None
    seconds: float


class LLMClient:
    """Chat completions and embeddings against settings.llm_base_url."""

    def __init__(self, settings: Settings, http: httpx.Client) -> None:
        self._base = settings.llm_base_url.rstrip("/")
        self._model = settings.llm_model
        self._embed_model = settings.embed_model
        self._embed_dim = settings.embed_dim
        self._headers = {"Authorization": f"Bearer {settings.llm_api_key.get_secret_value()}"}
        self._http = http

    @property
    def model(self) -> str:
        return self._model

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            resp = self._http.post(self._base + path, json=payload, headers=self._headers)
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LLMError(f"{path} failed: {type(exc).__name__}: {exc}") from exc

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        json_schema: dict[str, Any] | None = None,
        schema_name: str = "output",
        max_tokens: int = 600,
        seed: int = 7,
    ) -> ChatResult:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": 0,
            "seed": seed,
            "max_tokens": max_tokens,
        }
        if json_schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": schema_name, "schema": json_schema},
            }
        t0 = time.perf_counter()
        data = self._post("/chat/completions", payload)
        seconds = time.perf_counter() - t0
        try:
            content = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"unexpected chat response shape: {exc}") from exc
        usage = data.get("usage") or {}
        return ChatResult(
            content=content,
            completion_tokens=usage.get("completion_tokens"),
            prompt_tokens=usage.get("prompt_tokens"),
            seconds=seconds,
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        data = self._post("/embeddings", {"model": self._embed_model, "input": texts})
        try:
            rows = sorted(data["data"], key=lambda d: d["index"])
            out = [list(map(float, d["embedding"])) for d in rows]
        except (KeyError, TypeError) as exc:
            raise LLMError(f"unexpected embeddings response shape: {exc}") from exc
        if len(out) != len(texts) or any(len(v) != self._embed_dim for v in out):
            raise LLMError("embedding count or dimension does not match the request / EMBED_DIM")
        return out
