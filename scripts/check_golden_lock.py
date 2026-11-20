#!/usr/bin/env python3
"""Verify the pre-registered golden set against eval/golden/LOCK.json.

Recomputes the sha256 and question count of the locked file and fails loudly (exit 1) on any
mismatch, or if LOCK.json or the locked file is missing. Runs in CI.

Usage: uv run python scripts/check_golden_lock.py [--root PATH]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import yaml

LOCK = Path("eval/golden/LOCK.json")
REQUIRED = ("file", "sha256", "question_count", "locked_at_ist", "oracle_commit")


def check(root: Path) -> list[str]:
    """Return a list of problems; empty means the lock holds."""
    lock_path = root / LOCK
    if not lock_path.is_file():
        return [f"{LOCK} is missing: the golden set is not locked"]
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    missing = [k for k in REQUIRED if k not in lock]
    if missing:
        return [f"{LOCK} lacks fields: {missing}"]
    target = root / lock["file"]
    if not target.is_file():
        return [f"locked file {lock['file']} is missing"]
    data = target.read_bytes()
    problems = []
    digest = hashlib.sha256(data).hexdigest()
    if digest != lock["sha256"]:
        problems.append(f"{lock['file']} sha256 is {digest}, LOCK.json says {lock['sha256']}")
    count = len(yaml.safe_load(data)["questions"])
    if count != lock["question_count"]:
        problems.append(f"{lock['file']} has {count} questions, LOCK.json says {lock['question_count']}")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Verify eval/golden against LOCK.json")
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = ap.parse_args(argv)
    problems = check(args.root)
    if problems:
        print("GOLDEN LOCK BROKEN: the pre-registered eval set was changed after locking.", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        print(
            "Do not edit questions.yaml; put amendments in questions.v2.yaml (eval/golden/README.md).",
            file=sys.stderr,
        )
        return 1
    print(f"golden lock OK: {LOCK}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
