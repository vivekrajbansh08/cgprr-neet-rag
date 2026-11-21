"""CLI: verify raw files against MANIFEST.md, parse R1-R3 + seat matrices, load as neet_ingest.

Usage: uv run python -m neet_ingest
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import UTC, datetime

from neet_common.config import REPO_ROOT, Settings
from neet_common.db import connect

from neet_ingest.build import parse_all
from neet_ingest.load import load
from neet_ingest.manifest import ManifestError, read_manifest, verify

RAW_DIR = REPO_ROOT / "data" / "raw" / "mcc" / "2025"
MANIFEST = REPO_ROOT / "data" / "raw" / "MANIFEST.md"


def git_commit() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],  # noqa: S607 - git from PATH, fixed args
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.stdout.strip()


def main() -> int:
    started = datetime.now(UTC)
    t0 = time.perf_counter()
    manifest = read_manifest(MANIFEST)
    try:
        paths = verify(manifest, RAW_DIR)
    except ManifestError as exc:
        print(exc, file=sys.stderr)
        return 2
    t1 = time.perf_counter()
    print(f"verified {len(paths)} files against MANIFEST.md sha256 in {t1 - t0:.1f}s")
    parsed = parse_all(paths)
    t2 = time.perf_counter()
    print(f"parsed in {t2 - t1:.1f}s")
    with connect(Settings(), "neet_ingest") as conn:
        counts = load(conn, parsed, manifest, git_commit(), started)
    t3 = time.perf_counter()
    print(f"loaded in one transaction in {t3 - t2:.1f}s (total {t3 - t0:.1f}s)")
    print(json.dumps(counts, indent=2))
    print("chunk index cleared — run `make index`")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
