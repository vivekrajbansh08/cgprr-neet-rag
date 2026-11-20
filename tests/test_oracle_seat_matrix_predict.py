"""Seat-matrix state mapping (scripts/oracle_seat_matrix.py) and the predictor rule
(scripts/oracle_predict.py). Synthetic cases always run; real-file cases skip without the PDFs."""

from decimal import Decimal

import pytest


def entry(osm, code, state, name):
    return osm.SeatMatrixInstitute(code, state, name, "synthetic.pdf", 1)


def allot(op, rank, quota, inst, cat, remarks="Allotted", course="MBBS"):
    return op.Allotment(
        "synthetic.pdf", 1, 1, Decimal(rank), str(rank), quota, inst, course, cat, "General", remarks
    )


def test_state_needs_name_plus_city_not_a_generic_prefix(osm, op):
    entries = [
        entry(osm, "1", "Rajasthan", op.squash("Government Medical College, Tonk, Main Road")),
        entry(osm, "2", "Kerala", op.squash("Government Medical College, Kasaragod, Ukkinadka")),
    ]
    assert osm.state_of("Government Medical College, Tonk,Main Road, Rajasthan", entries).state == "Rajasthan"
    # Shares only "governmentmedicalcollege," with both entries: no match, not a guess.
    assert osm.state_of("Government Medical College, Jaisalmer, NH68", entries) is None


def test_equal_matches_in_two_states_are_an_error(osm, op):
    name = op.squash("Test Medical College, Alphatown, Road")
    entries = [entry(osm, "1", "Goa", name), entry(osm, "2", "Assam", name)]
    with pytest.raises(op.OracleError, match="states"):
        osm.state_of("Test Medical College, Alphatown, Road", entries)


def test_predictor_excludes_cw_and_nri_and_uses_seat_matrix_state(osm, op, opr):
    entries = [
        entry(osm, "1", "Goa", op.squash("Alpha Medical College, Panaji")),
        entry(osm, "2", "Assam", op.squash("Beta Medical College, Guwahati")),
    ]
    rows = [
        allot(op, 900, "All India", "Alpha Medical College, Panaji, Assam", "Open"),  # address says Assam
        allot(
            op,
            5000,
            "All India",
            "Alpha Medical College, Panaji, Assam",
            "Open",
            "Allotted( NRI Priority : 2 )",
        ),
        allot(op, 4000, "All India", "Beta Medical College, Guwahati", "OBC"),
        allot(op, 6000, "All India", "Beta Medical College, Guwahati", "OBC", "Allotted( CW Rank : 3 )"),
    ]
    goa = opr.predict(
        rows,
        entries,
        rank=Decimal(800),
        category="OBC",
        pwd=False,
        quota="All India",
        course="MBBS",
        state="Goa",
    )
    # Alpha is in Goa per the seat matrix (its address text says Assam); its NRI row is ignored.
    assert [(o.institute[:5], o.qualifying[0].rank_text) for o in goa.options] == [("Alpha", "900")]
    assam = opr.predict(
        rows,
        entries,
        rank=Decimal(5000),
        category="OBC",
        pwd=False,
        quota="All India",
        course="MBBS",
        state="Assam",
    )
    assert assam.options == []  # Beta OBC closes at 4000 once the CW row (6000) is excluded
    assert assam.max_closing.rank_text == "4000"


def test_eligible_categories(opr):
    assert opr.eligible_categories("General", False) == ("Open",)
    assert opr.eligible_categories("SC", True) == ("Open", "SC", "Open PwD", "SC PwD")


def test_real_every_r1_medical_and_dental_institute_has_a_state(parsed, seat_entries, osm):
    insts = {
        a.institute for a in parsed[1].allotments if a.course in ("MBBS", "BDS") and "Deemed" not in a.quota
    }
    insts -= {
        a.institute
        for a in parsed[1].allotments
        if a.quota
        in (
            "Non-Resident Indian",
            "Jain Minority Quota",
            "Muslim Minority Quota",
            "Employees State Insurance Scheme(ESI)",
        )
    }
    missing = [i for i in insts if osm.state_of(i, seat_entries) is None]
    assert missing == []
    assert len({e.state for e in seat_entries}) == 33


def test_real_anantnag_is_two_institutes_in_one_state(seat_entries):
    anantnag = sorted((e.code, e.state) for e in seat_entries if "anantnag" in e.name[:45])
    assert anantnag == [("200631", "Jammu And Kashmir"), ("200684", "Jammu And Kashmir")]
