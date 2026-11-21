"""Institute-name logic and RRF with invented names (no DB)."""

import pytest
from neet_retrieval.fusion import rrf
from neet_retrieval.names import IdfIndex, Scored, coverage, excluded, head, order_and_decide, short_name

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
    items = [
        Scored(
            id=i,
            fused=fused.get(i, 0.04),
            head_cov=coverage(query, head(n), IDF),
            name_cov=coverage(query, short_name(n), IDF),
            full_cov=coverage(query, n, IDF),
        )
        for i, n in NAMES.items()
        if not excluded(n, exclude)
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
