"""scripts/check_golden_lock.py: passes on the real lock, fails loudly on any tampering."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_golden_lock.py"
YAML = "questions:\n  - id: q1\n  - id: q2\n"


def run(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root)], capture_output=True, text=True, check=False
    )


def make_repo(tmp_path: Path, text: str = YAML, count: int = 2) -> Path:
    golden = tmp_path / "eval" / "golden"
    golden.mkdir(parents=True)
    (golden / "questions.yaml").write_text(text, encoding="utf-8")
    lock = {
        "file": "eval/golden/questions.yaml",
        "sha256": hashlib.sha256(text.encode()).hexdigest(),
        "question_count": count,
        "locked_at_ist": "2026-11-20T00:00:00+05:30",
        "oracle_commit": "0" * 40,
    }
    (golden / "LOCK.json").write_text(json.dumps(lock), encoding="utf-8")
    return tmp_path


def test_intact_lock_passes(tmp_path):
    assert run(make_repo(tmp_path)).returncode == 0


def test_edited_file_fails_loudly(tmp_path):
    root = make_repo(tmp_path)
    (root / "eval/golden/questions.yaml").write_text(YAML + "  - id: q3\n", encoding="utf-8")
    res = run(root)
    assert res.returncode == 1
    assert "GOLDEN LOCK BROKEN" in res.stderr
    assert "sha256" in res.stderr


def test_missing_lock_fails(tmp_path):
    root = make_repo(tmp_path)
    (root / "eval/golden/LOCK.json").unlink()
    assert run(root).returncode == 1


def test_the_real_golden_set_matches_its_lock():
    if not (ROOT / "eval/golden/LOCK.json").exists():
        pytest.skip("golden set not locked yet")
    res = run(ROOT)
    assert res.returncode == 0, res.stderr
