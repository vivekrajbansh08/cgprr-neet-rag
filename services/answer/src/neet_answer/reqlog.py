"""Append-only JSONL request log (logs/answer.log, gitignored). One line per /ask request."""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class RequestLog:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, record: dict[str, Any]) -> None:
        line = json.dumps({"ts": datetime.now(UTC).isoformat(), **record}, default=str, ensure_ascii=False)
        with self._lock, self._path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
