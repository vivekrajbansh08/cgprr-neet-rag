"""CLI: rebuild the retrieval index (neet.chunk) from the loaded rows, as neet_ingest.

Reads and embeds first (no transaction held open while embedding), then truncates and rewrites
neet.chunk in one fresh transaction. Every PDF read is verified against data/raw/MANIFEST.md first.
Chunks that look like instructions aimed at a model are logged and dropped (neet_ingest.screen).
Embeddings come from the local OpenAI-compatible endpoint.
Usage: uv run python -m neet_ingest.index
"""

from __future__ import annotations

import logging
import sys
import time

import httpx
from neet_common.config import REPO_ROOT, Settings
from neet_common.db import connect

from neet_ingest.chunks import Chunk, cell_chunks, legend_chunks, notice_chunks
from neet_ingest.embed import embed_batches
from neet_ingest.manifest import ManifestError, read_manifest, verify
from neet_ingest.screen import screen_chunks

RAW_DIR = REPO_ROOT / "data" / "raw" / "mcc" / "2025"
MANIFEST = REPO_ROOT / "data" / "raw" / "MANIFEST.md"
LEGEND_FILE = "r1_allotment_final.pdf"
NOTICES = {
    "r2_revision_notice": "r2_result_revision_notice.pdf",
    "r2_clarification_notice": "r2_result_clarification_notice.pdf",
}
COPY = (
    "COPY neet.chunk (kind, text, embedding, round, quota, institute_id, course, allotted_category,"
    " is_cw_nri, note, file, page, line) FROM STDIN"
)


def _vec(v: list[float]) -> str:
    return "[" + ",".join(repr(float(x)) for x in v) + "]"


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # one INFO line per batch is noise
    settings = Settings()
    manifest = read_manifest(MANIFEST)
    needed = {name: manifest[name] for name in (LEGEND_FILE, *NOTICES.values())}
    try:
        paths = verify(needed, RAW_DIR)
    except ManifestError as exc:
        print(exc, file=sys.stderr)
        return 2
    with connect(settings, "neet_ingest") as conn:
        if conn.execute("SELECT count(*) FROM neet.allotment").fetchone()[0] == 0:
            print("neet.allotment is empty: run `make ingest` first")
            return 2
        chunks: list[Chunk] = cell_chunks(conn)
        conn.commit()  # end the read transaction: nothing is held open while embedding
        chunks += legend_chunks(paths[LEGEND_FILE])
        chunks += notice_chunks({note: paths[name] for note, name in NOTICES.items()})
        chunks, dropped = screen_chunks(chunks)
        print(
            f"chunks: {len(chunks)} ({sum(c.kind == 'cell' for c in chunks)} cell);"
            f" dropped by injection screen: {len(dropped)}"
        )
        t0 = time.perf_counter()
        with httpx.Client(timeout=300) as client:
            vectors = embed_batches(client, settings, [c.text for c in chunks])
        dt = time.perf_counter() - t0
        print(f"embedded {len(vectors)} chunks in {dt:.1f}s ({len(vectors) / dt:.1f} chunks/s)")
        t1 = time.perf_counter()
        with conn.transaction(), conn.cursor() as cur:
            cur.execute("TRUNCATE neet.chunk")
            with cur.copy(COPY) as cp:
                for c, v in zip(chunks, vectors, strict=True):
                    cp.write_row(
                        (
                            c.kind, c.text, _vec(v), c.round, c.quota, c.institute_id, c.course,
                            c.allotted_category, c.is_cw_nri, c.note, c.file, c.page, c.line,
                        )
                    )  # fmt: skip
        print(f"wrote neet.chunk in one transaction in {time.perf_counter() - t1:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
