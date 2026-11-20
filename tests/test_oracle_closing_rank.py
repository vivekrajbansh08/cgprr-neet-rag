"""Tests for the independent closing-rank oracle (scripts/oracle_closing_rank.py, scripts/oracle_parse.py).

Two groups:
  * synthetic layout tests: hand-built `pdftotext -layout`-style text with invented institutes and
    ranks (no real allotment rows are committed). Each case is a layout trap seen in the real
    2025 files (docs/source_notes.md section 2 and 5). These always run.
  * real-file tests: parse data/raw/mcc/2025/*.pdf and pin counts and closing ranks. These skip
    when the PDFs (gitignored) or pdftotext are not available, e.g. in CI.
"""

import shutil
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "mcc" / "2025"


# ---------------------------------------------------------------- synthetic layout helpers

# Quota legend as printed on page 1 of every 2025 allotment PDF (public vocabulary, no rows).
LEGEND = [
    ("SA", "(AMU) Self finance All India"),
    ("SI", "(AMU)Self finance internal"),
    ("AM", "Aligarh Muslim University (AMU) Quota"),
    ("AI", "All India"),
    ("BS", "B.Sc Nursing All India"),
    ("BD", "B.Sc Nursing Delhi NCR"),
    ("BW", "B.Sc Nursing Delhi NCR CW Quota"),
    ("PW", "B.Sc Nursing IP CW Quota"),
    ("PS", "Deemed/Paid Seats Quota"),
    ("DW", "Delhi NCR Children/Widows of Personnel of the Armed Forces (CW) DU Quota"),
    ("IW", "Delhi NCR Children/Widows of Personnel of the Armed Forces (CW) IP Quota"),
    ("DU", "Delhi University Quota"),
    ("EN", "Employees State Insurance Scheme Nursing Quota (ESI-IP Quota Nursing)"),
    ("ES", "Employees State Insurance Scheme(ESI)"),
    ("FQ", "Foreign Country Quota"),
    ("JP", "Internal -Puducherry UT Domicile"),
    ("IP", "IP University Quota"),
    ("JM", "Jain Minority Quota"),
    ("JI", "Jamia Internal Quota"),
    ("MM", "Muslim Minority Quota"),
    ("JO", "Muslim OBC Quota"),
    ("MJ", "Muslim Quota"),
    ("JS", "Muslim ST Quota"),
    ("MW", "Muslim Women Quota"),
    ("NR", "Non-Resident Indian"),
    ("AN", "Non-Resident Indian(AMU)Quota"),
    ("JN", "Non-Resident Indian(Jamia)Quota"),
    ("SO", "Open Seat Quota"),
]
LEGEND_PAGE = "\n".join(
    ["              NEET-UG Counselling Seats Allotment -2025 Round X", "Abbrevation      Description"]
    + [f"   {code}                                   {desc}" for code, desc in LEGEND]
    + ["", "                         Allotted Category Abbrevations", "    BC          Other Backward Class"]
)


def cols(*cells: tuple[int, str]) -> str:
    """Place each text at its column (0-based), like pdftotext -layout does."""
    line = ""
    for x, text in cells:
        assert len(line) <= x, f"cell at {x} overlaps previous text {line!r}"
        line = line.ljust(x) + text
    return line


def parse(op, round_no: int, *rows: list[str]):
    page = "\n".join(line for row in rows for line in row)
    return op.parse_pages([LEGEND_PAGE, page], "synthetic.pdf", round_no)


# Round 1 columns: SNo, Rank, Quota, Institute, Course, Alloted Category, Candidate Category, Remarks
def r1(sno: int, rank: str, quota: str, inst: str, acat: str, ccat: str, course: str = "MBBS") -> str:
    return cols(
        (0, str(sno)),
        (7, rank),
        (15, quota),
        (36, inst),
        (97, course),
        (104, acat),
        (113, ccat),
        (124, "Allotted"),
    )


# ---------------------------------------------------------------- synthetic tests


def test_r1_row_with_wrapped_quota_and_wrapped_pwd(op):
    res = parse(
        op,
        1,
        [
            r1(1, "101", "Deemed/Paid Seats", "Test Medical College, Alpha,1 Main Road", "OBC", "OBC PwD"),
            cols((18, "Quota"), (40, "Alphatown, Testland, 100001"), (104, "PwD")),
        ],
    )
    (a,) = res.allotments
    assert a.quota == "Deemed/Paid Seats Quota"
    assert a.allotted_category == "OBC PwD"  # "PwD" wrapped under the allotted-category cell
    assert a.candidate_category == "OBC PwD"
    assert a.institute == "Test Medical College, Alpha,1 Main Road Alphatown, Testland, 100001"
    assert (a.page, a.line, a.rank) == (2, 1, Decimal(101))


def test_r1_quota_glued_to_institute_without_space(op):
    line1 = cols(
        (0, "1"),
        (7, "101"),
        (15, "Internal -PuducherryTEST INSTITUTE OF SCIENCE,"),
        (97, "MBBS"),
        (104, "EWS"),
        (113, "EWS"),
        (124, "Allotted"),
    )
    res = parse(op, 1, [line1, cols((19, "UT Domicile"))])
    (a,) = res.allotments
    assert a.quota == "Internal -Puducherry UT Domicile"
    assert a.institute == "TEST INSTITUTE OF SCIENCE,"


def test_fractional_rank_and_closing_rank_takes_numeric_max(op, oc):
    res = parse(
        op,
        1,
        [r1(1, "205", "All India", "Test Medical College, Alpha", "Open", "General")],
        [r1(2, "205.5", "All India", "Test Medical College, Alpha", "Open", "OBC")],
        [r1(3, "1000", "All India", "Test Medical College, Beta", "Open", "General")],
    )
    assert [a.rank_text for a in res.allotments] == ["205", "205.5", "1000"]
    cr = oc.closing_rank(res.allotments, "All India", "Test Medical College, Alpha", "MBBS", "Open")
    assert cr.closing_rank == Decimal("205.5")
    assert cr.matches == 2
    assert cr.row.rank_text == "205.5"


def test_closing_rank_refuses_to_pool_two_institutes(op, oc):
    res = parse(
        op,
        1,
        [r1(1, "10", "All India", "Test Medical College, Alpha Campus", "Open", "General")],
        [r1(2, "20", "All India", "Test Medical College, Alpha Campus North", "Open", "General")],
    )
    with pytest.raises(oc.AmbiguousInstituteError):
        oc.closing_rank(res.allotments, "All India", "Test Medical College, Alpha", "MBBS", "Open")
    cr = oc.closing_rank(res.allotments, "All India", "Alpha Campus North", "MBBS", "Open")
    assert cr.closing_rank == Decimal(20)


def test_no_matching_cell_gives_no_closing_rank(op, oc):
    res = parse(op, 1, [r1(1, "10", "All India", "Test Medical College, Alpha", "Open", "General")])
    cr = oc.closing_rank(res.allotments, "All India", "Test Medical College, Alpha", "MBBS", "SC")
    assert (cr.closing_rank, cr.matches, cr.row) == (None, 0, None)


def test_ranks_not_increasing_means_segmentation_is_wrong(op):
    with pytest.raises(op.OracleError, match="strictly increasing"):
        parse(
            op,
            1,
            [r1(1, "50", "All India", "Test Medical College, Alpha", "Open", "General")],
            [r1(2, "40", "All India", "Test Medical College, Alpha", "Open", "General")],
        )


# Round 2 columns: SNo, Rank, [R1: Quota, Institute, Course, Remarks], [R2: Quota, Institute,
# Course, Alloted Category, candidate Category, option No., Remarks]
R2X = (0, 6, 14, 27, 48, 56, 69, 83, 106, 113, 122, 132, 140)


def r2(*cells: str) -> str:
    return cols(*((x, c) for x, c in zip(R2X, cells, strict=False) if c))


def test_r2_rows_without_a_round_2_allotment_are_skipped(op):
    dashes = ["-"] * 6
    res = parse(
        op,
        2,
        [
            r2("1", "120", "Open Seat", "Test Inst Alpha", "MBBS", "Reported", *dashes, "Did not opt"),
            cols((14, "Quota"), (140, "for")),
            cols((140, "Upgradation.")),
        ],
        [
            r2("2", "130", "All India", "Test Inst Beta", "MBBS", "Reported", *dashes, "No"),
            cols((140, "Upgradation")),
        ],
        [
            r2("3", "140", "All India", "Test Inst Beta", "MBBS", "Not", *dashes, "Not Allotted."),
            cols((56, "Reported")),
        ],
        [r2("4", "150", "-", "-", "-", "-", *dashes, "Did not fill up"), cols((140, "fresh choices."))],
    )
    assert res.rows == 4
    assert res.allotments == []


def test_r2_surrendered_remark_touching_next_quota(op):
    line1 = r2(
        "1", "120", "Deemed/Pa", "Test Inst Beta", "MBBS", "Seat",
        "Deemed/Paid", "Test Inst Gamma", "MBBS", "Open", "General", "5", "Fresh Allotted",
    )  # fmt: skip
    line2 = cols(
        (15, "id Seats"),
        (27, "Betatown"),
        (56, "Surrendered Seats Quota"),
        (83, "Gammatown"),
        (140, "in 2nd Round"),
    )
    res = parse(op, 2, [line1, line2, cols((16, "Quota"))])
    (a,) = res.allotments
    assert a.quota == "Deemed/Paid Seats Quota"
    assert a.institute == "Test Inst Gamma Gammatown"
    assert a.remarks == "Fresh Allotted in 2nd Round"


def test_r2_row_that_looks_empty_but_mentions_an_allotment_is_an_error(op):
    dashes = ["-"] * 6
    with pytest.raises(op.OracleError, match="mentions an allotment"):
        parse(op, 2, [r2("1", "120", "-", "-", "-", "-", *dashes, "No"), cols((140, "Fresh Allotted"))])


# Round 3 columns: Rank, [R1: Q, I, C, Rem], [R2: Q, I, C, Rem], [R3: Q, I, C, ACat, CCat, Opt, Rem]
R3X = (0, 9, 20, 40, 48, 60, 72, 92, 100, 114, 126, 152, 160, 168, 177, 184)


def r3(*cells: str) -> str:
    return cols(*((x, c) for x, c in zip(R3X, cells, strict=False) if c))


def test_r3_dashes_then_quota_on_first_line_is_an_allotment(op):
    # Regression: eight "-" cells followed by the round-3 quota on the rank line, with institute and
    # tail one line lower. A loose "no allotment" pattern dropped 7 real rows like this.
    res = parse(
        op,
        3,
        [
            r3("32000", *["-"] * 8, "All India"),
            cols(
                (126, "TEST DENTAL COLLEGE"),
                (152, "BDS"),
                (160, "Open"),
                (168, "OBC"),
                (177, "3"),
                (184, "Fresh Allotted"),
            ),
            cols((127, "Testcity, 100002"), (184, "in 3nd Round")),
        ],
    )
    (a,) = res.allotments
    assert (a.quota, a.course, a.allotted_category) == ("All India", "BDS", "Open")
    assert a.institute == "TEST DENTAL COLLEGE Testcity, 100002"


def test_r3_quota_word_glued_on_continuation_line(op):
    res = parse(
        op,
        3,
        [
            r3(
                "700000",
                *["-"] * 8,
                "Non-",
                "Test Institute of",
                "MBBS",
                "Open",
                "OBC",
                "1",
                "Fresh Allotted",
            ),
            cols((114, "ResidentMedical Sciences,"), (184, "in 3nd Round")),
            cols((114, "Indian"), (127, "Testcity")),
        ],
    )
    (a,) = res.allotments
    assert a.quota == "Non-Resident Indian"
    assert a.institute == "Test Institute of Medical Sciences, Testcity"


def test_unrecognised_row_tail_is_an_error_not_a_skip(op):
    with pytest.raises(op.OracleError, match="row tail not recognised"):
        parse(op, 1, [cols((0, "1"), (7, "101"), (15, "All India"), (36, "Test College"), (97, "MD"))])


def test_squash_ignores_case_and_wrapped_whitespace(op):
    assert op.squash("TA MIL  NADU") == op.squash("Tamil Nadu") == "tamilnadu"


# ---------------------------------------------------------------- real-file tests

needs_pdfs = pytest.mark.skipif(
    shutil.which("pdftotext") is None or not (RAW / "r3_allotment_final.pdf").exists(),
    reason="raw MCC PDFs (gitignored) or pdftotext not available; run scripts/fetch_sources.sh",
)


@needs_pdfs
@pytest.mark.parametrize(
    ("round_no", "rows", "allotments"),
    [(1, 26608, 26608), (2, 35551, 15321), (3, 39479, 9143)],
)
def test_real_row_and_allotment_counts(parsed, round_no, rows, allotments):
    res = parsed[round_no]  # strict parse: any unrecognised row would have raised
    assert res.rows == rows
    assert len(res.allotments) == allotments
    assert res.failures == []
    assert len(res.quotas) == 28


@needs_pdfs
@pytest.mark.parametrize("round_no", [1, 2, 3])
def test_real_exactly_one_fractional_rank_per_round(parsed, round_no):
    fractional = [a for a in parsed[round_no].allotments if a.rank != a.rank.to_integral_value()]
    # R1: the fractional-rank row is allotted. R2/R3: it is allotted again (fresh/upgraded).
    assert len(fractional) == 1


# Closing ranks pinned for eval/golden/questions.yaml (aggregates only).
PINNED = [
    (1, "Open Seat Quota", "AIIMS, New Delhi", "MBBS", "Open", "48", 48, 4),
    (1, "Deemed/Paid Seats Quota", "Manipal Univ., Manipal", "MBBS", "Open", "40008", 212, 437),
    (3, "Deemed/Paid Seats Quota", "Manipal Univ., Manipal", "MBBS", "Open", "31834", 5, 640),
    (2, "Open Seat Quota", "JIPMER PUDUCHERRY", "MBBS", "OBC", "748", 1, 46),
    (1, "All India", "MADRAS MEDICAL COLLEGE", "MBBS", "SC", "6518", 6, 178),
    (
        2,
        "Employees State Insurance Scheme(ESI)",
        "ESIC Medical College, Gulbarga",
        "MBBS",
        "Open",
        "36944",
        17,
        1281,
    ),
    (3, "Delhi University Quota", "Lady Hardinge Medical College", "MBBS", "EWS", "15212", 1, 359),
]


@needs_pdfs
@pytest.mark.parametrize(("round_no", "quota", "inst", "course", "cat", "rank", "n", "page"), PINNED)
def test_real_pinned_closing_ranks(parsed, oc, round_no, quota, inst, course, cat, rank, n, page):
    cr = oc.closing_rank(parsed[round_no].allotments, quota, inst, course, cat)
    assert (cr.row.rank_text, cr.matches, cr.row.page) == (rank, n, page)
    assert cr.row.file == f"r{round_no}_allotment_final.pdf"


@needs_pdfs
def test_real_round1_allotments_equal_seat_matrix_seats(parsed, oc):
    # Seat matrix (seat_matrix_r1_aiims_bhu_jipmer.pdf): AIIMS New Delhi, Open Seat Quota, MBBS:
    # OP NO 48, BC NO 33, SC NO 18. Round 1 fills every seat, so allotment counts must match.
    a = parsed[1].allotments
    got = {
        c: oc.closing_rank(a, "Open Seat Quota", "AIIMS, New Delhi", "MBBS", c).matches
        for c in ("Open", "OBC", "SC")
    }
    assert got == {"Open": 48, "OBC": 33, "SC": 18}


@needs_pdfs
def test_real_cell_with_no_round3_allotment(parsed, oc):
    cr = oc.closing_rank(parsed[3].allotments, "Open Seat Quota", "AIIMS, New Delhi", "MBBS", "Open")
    assert cr.closing_rank is None


@needs_pdfs
def test_real_ambiguous_institute_substring_is_refused(parsed, oc):
    with pytest.raises(oc.AmbiguousInstituteError) as exc:
        oc.closing_rank(
            parsed[1].allotments,
            "Deemed/Paid Seats Quota",
            "Kasturba Medical College, Manipal",
            "MBBS",
            "Open",
        )
    assert len(exc.value.institutes) == 2


@needs_pdfs
def test_real_cli_prints_closing_rank_and_source(oc, capsys):
    rc = oc.main(
        [
            "--round",
            "1",
            "--quota",
            "Open Seat Quota",
            "--institute",
            "AIIMS, New Delhi",
            "--course",
            "MBBS",
            "--category",
            "Open",
        ]
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert "closing_rank: 48" in out
    assert "matches: 48" in out
    assert "source: r1_allotment_final.pdf page 4 line 47" in out
