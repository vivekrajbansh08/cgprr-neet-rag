"""Institute-name logic and RRF with invented names (no DB)."""

import pytest
from neet_retrieval.fusion import rrf
from neet_retrieval.names import (
    IdfIndex,
    core_name,
    coverage,
    excluded,
    name_part,
    order_and_decide,
    score,
    short_name,
)

NAMES = {
    1: "Alpha Medical College, Univ., Northtown,Hill Road, Northtown, Somestate, 100001",
    2: "Alpha Medical College, Univ., Southtown,Light Road, Southtown, Somestate, 100002",
    3: "BETA KARAIKAL,BETA Academic Campus, Karaikal, Coastal, 100003",
    4: "BETA PUDUCHERRY,Gorimedu Puducherry, Coastal, 100004",
    5: "Gamma Government Medical College, Westcity,Main Road, Somestate, 100005",
    6: "College of Nursing Delta, Gamma Government Medical College,Westcity, 100006",
    7: "Epsilon Medical College, Westcity,Station Road, Somestate, 100007",
}
IDF = IdfIndex.build(NAMES.values())


def decide(query, exclude=(), fused=None):
    fused = fused or {}
    return decide_in(NAMES, IDF, query, exclude, fused)


def decide_in(names, idf, query, exclude=(), fused=None):
    fused = fused or {}
    items = [
        score(i, fused.get(i, 0.04), query, n, idf) for i, n in names.items() if not excluded(n, exclude)
    ]
    ranked, status = order_and_decide(items)
    return [s.id for s in ranked], status


def test_rrf_scores_and_ranks():
    scores, ranks = rrf({"a": [1, 2], "b": [2, 3]}, k=60)
    assert scores[2] == pytest.approx(1 / 62 + 1 / 61)
    assert ranks[3] == {"a": None, "b": 2}
    assert max(scores, key=scores.get) == 2


def test_short_name_stops_before_address_digits():
    assert short_name(NAMES[1]) == "Alpha Medical College, Univ., Northtown"
    assert not any(ch.isdigit() for ch in short_name(NAMES[5]))


def test_shared_campus_name_is_ambiguous():
    _, status = decide("Alpha Univ")
    assert status == "ambiguous"


def test_city_named_in_one_campus_resolves():
    ids, status = decide("Alpha Medical College Southtown")
    assert (ids[0], status) == (2, "resolved")


def test_explicit_exclusion_resolves_the_other_campus():
    ids, status = decide("Alpha Medical College", exclude=["Southtown"])
    assert (ids[0], status) == (1, "resolved")


def test_bare_short_name_matching_two_institutes_is_ambiguous():
    assert decide("BETA")[1] == "ambiguous"
    ids, status = decide("BETA Puducherry")
    assert (ids[0], status) == (4, "resolved")


def test_name_in_own_head_beats_name_inside_another_institute_string():
    ids, status = decide("Gamma Government Medical College")
    assert (ids[0], status) == (5, "resolved")


def test_unknown_institute_is_not_found():
    assert decide("Zeta Armed Forces Medical College, Westcity")[1] == "not_found"


def test_spelling_variant_matches():
    assert coverage("Epsilonn Medical College", NAMES[7], IDF) == pytest.approx(1.0)


def test_long_form_alias_expands():
    from neet_retrieval.names import expand_aliases

    assert expand_aliases("All India Institute of Medical Sciences, Northtown") == "aiims, northtown"


def test_short_name_stops_at_address_restating_the_name():
    assert (
        short_name("GAMMA COLLEGE, WESTCITY,GAMMA COLLEGE MAIN ROAD, Somestate, 100001")
        == "GAMMA COLLEGE, WESTCITY"
    )


def test_coverage_tie_is_ambiguous_even_with_very_different_fused_scores():
    _, status = decide("Alpha Univ", fused={1: 0.05, 2: 0.001})
    assert status == "ambiguous"


# Invented names in the MCC "<name>,<address>" shape: the name's own commas have a space after them.
CAMPUS = {
    11: "OMEGA, Northtown,RIVER PHASE - II, NORTHTOWN-100011, Somestate, 100011",
    12: "OMEGA Easttown ,Northtown Village near Market Road Easttown, Otherstate, 100012",
    13: "Sigma Medical College, Delta Univ., Hilltop,Light house Road, Hilltop, Somestate, 100013",
    14: "Sigma Medical College, Delta Univ., Delta,Madhav Nagar, Delta, Somestate, 100014",
    15: "KAPPA LAKESIDE,KAPPA Academic Campus, Lakeside, Coastal, 100015",
    16: "KAPPA SEASIDE,Gorimedu Seaside, Coastal, 100016",
}
CAMPUS_IDF = IdfIndex.build(CAMPUS.values())


def test_name_part_and_core_name_drop_the_address():
    assert name_part(CAMPUS[11]) == "OMEGA, Northtown"
    assert name_part(CAMPUS[12]) == "OMEGA Easttown"
    assert core_name(CAMPUS[13]) == "Sigma Medical College Hilltop"
    assert core_name(CAMPUS[15]) == "KAPPA LAKESIDE"


def test_city_in_another_institutes_address_is_not_ambiguous():
    ids, status = decide_in(CAMPUS, CAMPUS_IDF, "OMEGA Northtown")
    assert (ids[0], status) == (11, "resolved")


def test_campus_city_resolves_when_head_is_shared():
    ids, status = decide_in(CAMPUS, CAMPUS_IDF, "Sigma Medical College Delta")
    assert (ids[0], status) == (14, "resolved")
    ids, status = decide_in(CAMPUS, CAMPUS_IDF, "Sigma Medical College Hilltop")
    assert (ids[0], status) == (13, "resolved")


def test_shared_name_without_city_stays_ambiguous():
    assert decide_in(CAMPUS, CAMPUS_IDF, "Sigma Medical College")[1] == "ambiguous"
    assert decide_in(CAMPUS, CAMPUS_IDF, "KAPPA")[1] == "ambiguous"
    ids, status = decide_in(CAMPUS, CAMPUS_IDF, "KAPPA Seaside")
    assert (ids[0], status) == (16, "resolved")


# MCC also prints a tight comma between a one-part name and its city ("GOVT. X COLLEGE,TOWN,...").
TIGHT = {
    21: "GOVT. OMEGA COLLEGE,RIVERTON,Government Omega College Campus, Somestate, 100021",
    22: "MU Omega College, Riverton,Station Road, Riverton, Somestate, 100022",
    23: "Government Omega College, Lakeview,Main Road, Somestate, 100023",
    24: "Govt Omega College Hilltown Somestate,NH-1, Somestate, 100024",
    25: "Government Omega College, Dalesford, Somestate,Old Road, 100025",
}
TIGHT_IDF = IdfIndex.build(TIGHT.values())


def test_tight_comma_city_and_govt_abbreviation_resolve_to_the_right_college():
    assert name_part(TIGHT[21]) == "GOVT. OMEGA COLLEGE, RIVERTON"
    for q in ("Government Omega College Riverton", "Govt Omega College Riverton"):
        ids, status = decide_in(TIGHT, TIGHT_IDF, q)
        assert (ids[0], status) == (21, "resolved"), q


def test_generic_head_with_state_word_is_ambiguous_not_a_winner():
    _, status = decide_in(TIGHT, TIGHT_IDF, "Government Omega College Somestate")
    assert status == "ambiguous"


def test_middle_part_typed_in_full_is_not_read_as_the_city():
    ids, status = decide_in(CAMPUS, CAMPUS_IDF, "Sigma Medical College Delta Univ")
    assert status == "ambiguous" and {13, 14} <= set(ids)


def test_address_can_only_send_to_clarify_never_pick_a_winner():
    names = {
        31: "Rho Medical Sciences, Delta,Westcity, Somestate, 100031",
        32: "Rho Nursing College, Westcity,Rho Medical Sciences Road, Somestate, 100032",
    }
    idf = IdfIndex.build(names.values())
    # Neither name explains "Westcity" + "Medical Sciences"; both full strings cover the query.
    assert decide_in(names, idf, "Rho Medical Sciences Westcity")[1] == "ambiguous"
