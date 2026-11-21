"""pdftotext access and text normalisation shared by every MCC parser."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path


class OracleError(RuntimeError):
    """The text layout did not match what the parser expects."""


def squash(text: str) -> str:
    """Lower-case, all whitespace removed: makes matching immune to line wraps inside words."""
    return re.sub(r"\s+", "", text).lower()


def pdftotext_pages(pdf: Path, first: int | None = None, last: int | None = None) -> list[str]:
    """`pdftotext -layout` text of a PDF, one string per page (split on form feeds)."""
    exe = shutil.which("pdftotext")
    if exe is None:
        raise OracleError("pdftotext not found (brew install poppler)")
    args = [exe, "-layout"]
    if first is not None:
        args += ["-f", str(first)]
    if last is not None:
        args += ["-l", str(last)]
    out = subprocess.run(  # noqa: S603 - fixed executable, list args, no shell
        [*args, str(pdf), "-"], check=True, capture_output=True, text=True
    ).stdout
    return out.split("\f")
