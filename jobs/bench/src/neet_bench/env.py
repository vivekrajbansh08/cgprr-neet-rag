"""Environment capture for a bench run: hardware, OS, Ollama version, model metadata, git commit.

Every probe is best-effort: a failure is recorded as an error string, never raised.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import Any

import httpx


def _run(argv: list[str]) -> str | None:
    exe = shutil.which(argv[0])
    if exe is None:
        return None
    try:
        out = subprocess.run(  # noqa: S603 - fixed argv, resolved executable
            [exe, *argv[1:]], capture_output=True, text=True, timeout=15, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def hardware() -> dict[str, Any]:
    mem = _run(["sysctl", "-n", "hw.memsize"])
    return {
        "cpu": _run(["sysctl", "-n", "machdep.cpu.brand_string"]),
        "memory_bytes": int(mem) if mem and mem.isdigit() else None,
        "memory_gib": round(int(mem) / 2**30, 1) if mem and mem.isdigit() else None,
        "os": _run(["sw_vers"]),
        "gpu": _run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"]),
    }


def git_commit(cwd: str) -> dict[str, Any]:
    commit = _run(["git", "-C", cwd, "rev-parse", "HEAD"])
    status = _run(["git", "-C", cwd, "status", "--porcelain", "--untracked-files=no"])
    return {"commit": commit, "dirty": bool(status) if status is not None else None}


def native_base(llm_base_url: str) -> str:
    """Ollama's native API root from the OpenAI-compatible base (strip a trailing /v1)."""
    base = llm_base_url.rstrip("/")
    return base[: -len("/v1")] if base.endswith("/v1") else base


def _licence_line(text: str | None) -> str | None:
    for line in (text or "").splitlines():
        if line.strip():
            return line.strip()
    return None


def model_info(client: httpx.Client, base: str, model: str) -> dict[str, Any]:
    """Digest, quantisation, parameter count, context length and licence line via Ollama /api/*."""
    out: dict[str, Any] = {"name": model}
    try:
        tags = client.get(base + "/api/tags").json().get("models") or []
        want = {model, model if ":" in model else model + ":latest"}
        hit = next((m for m in tags if m.get("name") in want or m.get("model") in want), None)
        out["digest"] = hit.get("digest") if hit else None
        out["size_bytes"] = hit.get("size") if hit else None
    except (httpx.HTTPError, ValueError) as exc:
        out["tags_error"] = f"{type(exc).__name__}: {exc}"
    try:
        resp = client.post(base + "/api/show", json={"model": model})
        resp.raise_for_status()
        show = resp.json()
        details = show.get("details") or {}
        info = show.get("model_info") or {}
        out["format"] = details.get("format")
        out["family"] = details.get("family")
        out["parameter_size"] = details.get("parameter_size")
        out["quantization_level"] = details.get("quantization_level")
        out["parameter_count"] = info.get("general.parameter_count")
        ctx = [v for k, v in info.items() if k.endswith(".context_length")]
        out["context_length"] = ctx[0] if ctx else None
        out["licence_line"] = _licence_line(show.get("license"))
    except (httpx.HTTPError, ValueError) as exc:
        out["show_error"] = f"{type(exc).__name__}: {exc}"
    return out


def capture(client: httpx.Client, llm_base_url: str, models: list[str], repo_root: str) -> dict[str, Any]:
    base = native_base(llm_base_url)
    try:
        api_version = client.get(base + "/api/version").json().get("version")
    except (httpx.HTTPError, ValueError):
        api_version = None
    try:
        loaded = [m.get("name") for m in client.get(base + "/api/ps").json().get("models") or []]
    except (httpx.HTTPError, ValueError):
        loaded = None
    return {
        "hardware": hardware(),
        "git": git_commit(repo_root),
        "llm_base_url": llm_base_url,
        "ollama_cli_version": _run(["ollama", "--version"]),
        "ollama_api_version": api_version,
        "ollama_loaded_models_at_start": loaded,
        "models": [model_info(client, base, m) for m in models if m],
    }
