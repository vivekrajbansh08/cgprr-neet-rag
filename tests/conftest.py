"""Shared fixtures for the oracle tests: the oracle modules (scripts/oracle_*.py) and, when the
raw MCC PDFs are present, the parsed 2025 allotments and seat-matrix states (parsed once per run).

Fixtures that need the PDFs skip the test when the PDFs (gitignored) or pdftotext are missing,
e.g. in CI. Fetch them with scripts/fetch_sources.sh.
"""

import importlib
import shutil
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "mcc" / "2025"


def _import_script(name: str) -> ModuleType:
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    return importlib.import_module(name)


def pdfs_available() -> bool:
    return shutil.which("pdftotext") is not None and (RAW / "r3_allotment_final.pdf").exists()


@pytest.fixture(scope="session")
def op() -> ModuleType:
    return _import_script("oracle_parse")


@pytest.fixture(scope="session")
def oc() -> ModuleType:
    return _import_script("oracle_closing_rank")


@pytest.fixture(scope="session")
def osm() -> ModuleType:
    return _import_script("oracle_seat_matrix")


@pytest.fixture(scope="session")
def opr() -> ModuleType:
    return _import_script("oracle_predict")


@pytest.fixture(scope="session")
def parsed(op):
    if not pdfs_available():
        pytest.skip("raw MCC PDFs (gitignored) or pdftotext not available; run scripts/fetch_sources.sh")
    return {r: op.parse_allotments(RAW / f"r{r}_allotment_final.pdf", r) for r in (1, 2, 3)}


@pytest.fixture(scope="session")
def seat_entries(osm):
    if not pdfs_available():
        pytest.skip("raw MCC PDFs (gitignored) or pdftotext not available; run scripts/fetch_sources.sh")
    return osm.load_seat_matrices(RAW)
