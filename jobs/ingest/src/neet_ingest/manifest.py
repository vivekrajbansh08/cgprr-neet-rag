"""data/raw/MANIFEST.md: the sha256-pinned list of raw MCC files. Ingest refuses any mismatch."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from pydantic import BaseModel

BASE_URL = re.compile(r"\*\*Base URL:\*\*\s*`([^`]+)`")
ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|")


class ManifestError(RuntimeError):
    """MANIFEST.md is malformed, or a raw file is missing or does not match its sha256."""


class ManifestEntry(BaseModel):
    local: str  # path under data/raw/mcc/2025, e.g. "notices/r2_result_revision_notice.pdf"
    url: str
    retrieved_at: str
    pages: int
    sha256: str

    @property
    def file_name(self) -> str:
        return Path(self.local).name


def read_manifest(path: Path) -> dict[str, ManifestEntry]:
    """Entries keyed by file name (basename)."""
    text = path.read_text(encoding="utf-8")
    base = BASE_URL.search(text)
    if base is None:
        raise ManifestError("MANIFEST.md has no **Base URL:** line")
    out: dict[str, ManifestEntry] = {}
    for line in text.splitlines():
        if not ROW.match(line):
            continue
        cells = [c.strip().strip("`") for c in line.strip().strip("|").split("|")]
        if len(cells) != 7:
            raise ManifestError(f"unexpected manifest row: {line[:80]!r}")
        local, _, url, retrieved, _, pages, sha = cells
        if not re.fullmatch(r"[0-9a-f]{64}", sha):
            raise ManifestError(f"bad sha256 for {local}")
        entry = ManifestEntry(
            local=local, url=base.group(1) + url, retrieved_at=retrieved, pages=int(pages), sha256=sha
        )
        if entry.file_name in out:
            raise ManifestError(f"duplicate file name in MANIFEST.md: {entry.file_name}")
        out[entry.file_name] = entry
    if not out:
        raise ManifestError("no file rows in MANIFEST.md")
    return out


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def verify(entries: dict[str, ManifestEntry], raw_dir: Path) -> dict[str, Path]:
    """Path of every manifest file, after checking it exists and matches its sha256. Raises on the
    first problem, listing all of them."""
    problems: list[str] = []
    paths: dict[str, Path] = {}
    for name, e in entries.items():
        p = raw_dir / e.local
        if not p.is_file():
            problems.append(f"missing: {p}")
            continue
        got = sha256_of(p)
        if got != e.sha256:
            problems.append(f"sha256 mismatch: {p} (manifest {e.sha256[:12]}…, file {got[:12]}…)")
        paths[name] = p
    if problems:
        raise ManifestError("refusing to ingest:\n  " + "\n  ".join(problems))
    return paths
