#!/usr/bin/env python3
"""Institute -> state from the MCC Round 1 seat matrices (`pdftotext -layout` + regex), part of the
oracle. The state comes from the seat matrix StateName column, never from allotment address text.

The logic lives in libs/mccparse (neet_mccparse.seat_matrix); this module re-exports it.
"""

from neet_mccparse.seat_matrix import (
    CITY_CHARS,
    LONG_LAYOUT_FILES,
    MIN_PREFIX,
    SeatMatrixInstitute,
    load_seat_matrices,
    parse_seat_matrix,
    required_prefix,
    state_of,
)

__all__ = [
    "CITY_CHARS",
    "LONG_LAYOUT_FILES",
    "MIN_PREFIX",
    "SeatMatrixInstitute",
    "load_seat_matrices",
    "parse_seat_matrix",
    "required_prefix",
    "state_of",
]
