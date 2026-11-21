"""Prompt-injection screen for retrieval chunks (project rules in README.md).

Retrieved text is data, never instructions. Chunks that look like instructions aimed at a model are
logged and dropped before they reach the index. The pattern list is deliberately small and literal;
it is a tripwire, not a classifier. The citation verifier remains the main control.
"""

from __future__ import annotations

import logging
import re

from neet_ingest.chunks import Chunk

log = logging.getLogger(__name__)

INJECTION_PATTERNS = (
    re.compile(r"\bignore\s+(?:all\s+|any\s+)?(?:previous|prior|above|earlier|the)?\s*instructions\b", re.I),
    re.compile(r"\bdisregard\b.{0,40}\binstructions\b", re.I | re.S),
    re.compile(r"\bsystem\s+prompt\b", re.I),
    re.compile(r"\byou\s+are\s+now\b", re.I),
    re.compile(r"\bact\s+as\s+(?:a|an|the|if)\b", re.I),
    re.compile(r"\breveal\b.{0,40}\bprompt\b", re.I | re.S),
)


def looks_like_injection(text: str) -> str | None:
    """The first matching pattern, or None for clean text."""
    for pat in INJECTION_PATTERNS:
        if pat.search(text):
            return pat.pattern
    return None


def screen_chunks(chunks: list[Chunk]) -> tuple[list[Chunk], list[Chunk]]:
    """(kept, dropped). Every dropped chunk is logged with its source pointer and the pattern."""
    kept: list[Chunk] = []
    dropped: list[Chunk] = []
    for c in chunks:
        hit = looks_like_injection(c.text)
        if hit is None:
            kept.append(c)
            continue
        log.warning(
            "dropped chunk that looks like instructions: %s p%s l%s (pattern %s)", c.file, c.page, c.line, hit
        )
        dropped.append(c)
    return kept, dropped
