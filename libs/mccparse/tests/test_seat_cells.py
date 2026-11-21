"""neet_mccparse.seat_cells on synthetic pages (invented institutes and numbers, never real rows),
plus real-file checks that skip when the raw MCC PDFs are absent."""

import shutil
from pathlib import Path

import pytest
from neet_mccparse.allotments import read_quota_legend
from neet_mccparse.seat_cells import category_of, parse_long_page, parse_seat_cells, parse_wide_page
from neet_mccparse.text import OracleError, pdftotext_pages

QUOTAS = (
    "All India",
    "Open Seat Quota",
    "Internal -Puducherry UT Domicile",
    "Delhi NCR Children/Widows of Personnel of the Armed Forces (CW) DU Quota",
    "Delhi University Quota",
    "Deemed/Paid Seats Quota",
    "Non-Resident Indian",
    "Employees State Insurance Scheme(ESI)",
)


def row(state="", typ="", inst="", quota="", tail=""):
    """One long-layout line: StateName | InstituteType | Institute | Quota | Branch Category Seats."""
    return f"{state:<14}{typ:<16}{inst:<44}{quota:<32}{tail}".rstrip()


OP_PH_2 = "MBBS (MBBS)    OP PH        2"


def long_page(*records):
    return "\n".join(["Page 1 of 1", "StateName  InstituteType  Institute  Quota", *records, ""])


def test_category_codes():
    assert category_of("OP PH") == "Open PwD"
    assert category_of("BC NO") == "OBC"
    assert category_of("EW NO") == "EWS"
    with pytest.raises(OracleError):
        category_of("GN NO")


def test_long_layout_wrapped_quota_spans_lines_above_and_below():
    page = long_page(
        row(typ="Typeone", inst="Alpha Medical College, Testville,"),
        row("Testland", "Typeone", "Main Road", "All India", "MBBS (MBBS)    OP NO        7"),
        row(typ="Typeone", inst="Testville (900001)"),
        row(typ="Typeone", inst="Alpha Medical College, Testville,", quota="Delhi NCR Children/Widows of"),
        row("Testland", "Typeone", "Main Road", "Personnel of the Armed Forces", OP_PH_2),
        row(typ="Typeone", inst="Testville (900001)", quota="(CW) DU Quota"),
    )
    cells = parse_long_page("synthetic.pdf", 1, page, QUOTAS)
    assert [(c.code, c.state, c.quota, c.course, c.category, c.seats, c.line) for c in cells] == [
        ("900001", "Testland", "All India", "MBBS", "Open", 7, 4),
        (
            "900001",
            "Testland",
            "Delhi NCR Children/Widows of Personnel of the Armed Forces (CW) DU Quota",
            "MBBS",
            "Open PwD",
            2,
            7,
        ),
    ]


def test_long_layout_quota_glued_to_institute_and_quota_off_the_seat_line():
    page = long_page(
        row(typ="Typeone", inst="Beta College, Sampletown", quota="Open Seat Quota", tail=""),
        row("Testland", "Typeone", "Road (900002)", "Open Seat Quota", "BDS (BDS)    SC NO        3"),
        # quota glued to the institute text by one space, on the seat line itself
        row("Testland", "Typeone", "")
        + "Gamma College, Sampletown, Long Address Text (900003) All India   MBBS (MBBS)    ST NO     1",
        # quota printed above and below a seat line that carries none; glued above
        row(typ="Typeone", inst="Delta College, Far Road, Internal -Puducherry UT"),
        row("Testland", "Typeone", "", "", "MBBS (MBBS)    BC NO        4"),
        row(typ="Typeone", inst="Delta Town (900004)", quota="Domicile"),
    )
    cells = parse_long_page("synthetic.pdf", 1, page, QUOTAS)
    assert [(c.code, c.quota, c.category, c.seats) for c in cells] == [
        ("900002", "Open Seat Quota", "SC", 3),
        ("900003", "All India", "ST", 1),
        ("900004", "Internal -Puducherry UT Domicile", "OBC", 4),
    ]


def test_long_layout_unknown_quota_raises():
    page = long_page(
        row(typ="Typeone", inst="Alpha Medical College, Testville,"),
        row("Testland", "Typeone", "Main Road", "All India", "MBBS (MBBS)    OP NO        7"),
        row(typ="Typeone", inst="Testville (900001)"),
        row(typ="Typeone", inst="Alpha Medical College, Testville,"),
        row("Testland", "Typeone", "Main Road", "Made Up Quota", "MBBS (MBBS)    OP NO        7"),
        row(typ="Typeone", inst="Testville (900001)"),
    )
    with pytest.raises(OracleError, match="quota not recognised"):
        parse_long_page("synthetic.pdf", 1, page, QUOTAS)


ESI_NUMS = "     ".join(["5", "1", "2", "0", "3", "0", "1", "0", "1", "0", "13"])
NRI_NUMS = "     ".join(["4", "0", "0", "0", "0", "0", "0", "0", "0", "0", " 4"])
WIDE = "\n".join(
    [
        "Page 1 of 1",
        "FINAL SEAT MATRIX FOR SYNTHETIC",
        " " * 78 + "General-   General-",
        "  Institute Type          Institute               Program   Quota            Open  Open PwD",
        " " * 79 + "EWS       EWS PwD",
        "                    Epsilon Medical College,                       Employees State Insurance",
        "Deemed University     Sampletown(900005)          MBBS      Scheme(ESI)            " + ESI_NUMS,
        "Deemed University     Zeta College, Town(900006)  BDS       Non-Resident Indian    " + NRI_NUMS,
        "",
    ]
)


def test_wide_layout_columns_and_wrapped_quota():
    cells = parse_wide_page("synthetic_wide.pdf", 1, WIDE, QUOTAS)
    got = [(c.code, c.state, c.quota, c.course, c.category, c.seats) for c in cells]
    esi = "Employees State Insurance Scheme(ESI)"
    assert got == [
        ("900005", None, esi, "MBBS", "Open", 5),
        ("900005", None, esi, "MBBS", "Open PwD", 1),
        ("900005", None, esi, "MBBS", "EWS", 2),
        ("900005", None, esi, "MBBS", "OBC", 3),
        ("900005", None, esi, "MBBS", "SC", 1),
        ("900005", None, esi, "MBBS", "ST", 1),
        ("900006", None, "Non-Resident Indian", "BDS", "Open", 4),
    ]


def test_wide_layout_total_mismatch_raises():
    bad = WIDE.replace(NRI_NUMS, NRI_NUMS[:-1] + "5")
    with pytest.raises(OracleError, match="do not add up"):
        parse_wide_page("synthetic_wide.pdf", 1, bad, QUOTAS)


RAW = Path(__file__).resolve().parents[3] / "data" / "raw" / "mcc" / "2025"
NAMES = (
    "seat_matrix_r1_aiq_except_cu.pdf",
    "seat_matrix_r1_aiims_bhu_jipmer.pdf",
    "seat_matrix_r1_central_universities.pdf",
    "seat_matrix_r1_deemed.pdf",
    "seat_matrix_r1_esic_ip.pdf",
)


@pytest.mark.skipif(
    shutil.which("pdftotext") is None or not (RAW / NAMES[0]).exists(), reason="raw MCC PDFs not available"
)
def test_real_every_seat_matrix_parses_into_legend_vocabulary():
    legend = read_quota_legend(pdftotext_pages(RAW / "r1_allotment_final.pdf", 1, 2))
    for name in NAMES:
        cells = parse_seat_cells(RAW / name, legend)
        assert cells, name
        assert {c.quota for c in cells} <= set(legend)
        assert all(c.seats > 0 and c.course in ("MBBS", "BDS") for c in cells)
        if name in ("seat_matrix_r1_deemed.pdf", "seat_matrix_r1_esic_ip.pdf"):
            assert {c.state for c in cells} == {None}
        else:
            assert None not in {c.state for c in cells}
