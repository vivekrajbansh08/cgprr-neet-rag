#!/usr/bin/env python3
"""Row parser for MCC NEET-UG allotment PDFs (`pdftotext -layout` + regex), part of the oracle.

The logic lives in libs/mccparse (neet_mccparse.allotments) so that the oracle and jobs/ingest share
one parser. This module re-exports it under the names the oracle scripts and tests use.
"""

from neet_mccparse.allotments import (
    CAND_CATEGORIES,
    CATEGORIES,
    COURSES,
    Allotment,
    ParseResult,
    parse_allotments,
    parse_pages,
    read_quota_legend,
)
from neet_mccparse.text import OracleError, pdftotext_pages, squash

__all__ = [
    "CAND_CATEGORIES",
    "CATEGORIES",
    "COURSES",
    "Allotment",
    "OracleError",
    "ParseResult",
    "parse_allotments",
    "parse_pages",
    "pdftotext_pages",
    "read_quota_legend",
    "squash",
]
