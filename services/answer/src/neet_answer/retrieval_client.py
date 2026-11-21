"""HTTP client for the retrieval service (RETRIEVAL_URL). Services never import each other."""

from __future__ import annotations

from typing import Protocol

import httpx
from neet_common.schemas import (
    CellsRequest,
    CellsResponse,
    InstituteInfo,
    InstituteNames,
    ResolveRequest,
    ResolveResponse,
)


class RetrievalError(RuntimeError):
    """The retrieval service was unreachable or returned an error."""


class Retrieval(Protocol):
    def resolve(self, req: ResolveRequest) -> ResolveResponse: ...

    def cells(self, req: CellsRequest) -> CellsResponse: ...

    def institute_names(self) -> list[str]: ...

    def institute(self, institute_id: int) -> InstituteInfo | None: ...


class HttpRetrieval:
    def __init__(self, base_url: str, http: httpx.Client) -> None:
        self._base = base_url.rstrip("/")
        self._http = http

    def _post(self, path: str, body: dict[str, object]) -> dict[str, object]:
        try:
            resp = self._http.post(self._base + path, json=body)
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise RetrievalError(f"retrieval {path} failed: {type(exc).__name__}: {exc}") from exc

    def resolve(self, req: ResolveRequest) -> ResolveResponse:
        return ResolveResponse.model_validate(self._post("/resolve_institute", req.model_dump()))

    def cells(self, req: CellsRequest) -> CellsResponse:
        return CellsResponse.model_validate(self._post("/cells", req.model_dump()))

    def institute_names(self) -> list[str]:
        try:
            resp = self._http.get(self._base + "/institute_names")
            resp.raise_for_status()
            return InstituteNames.model_validate(resp.json()).names
        except (httpx.HTTPError, ValueError) as exc:
            raise RetrievalError(f"retrieval /institute_names failed: {type(exc).__name__}: {exc}") from exc

    def institute(self, institute_id: int) -> InstituteInfo | None:
        """The catalog institute with this id, or None when there is no such institute (404)."""
        try:
            resp = self._http.get(f"{self._base}/institutes/{int(institute_id)}")
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return InstituteInfo.model_validate(resp.json())
        except (httpx.HTTPError, ValueError) as exc:
            raise RetrievalError(f"retrieval /institutes failed: {type(exc).__name__}: {exc}") from exc
