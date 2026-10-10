import pytest

from trips.domain.geo import LatLon
from trips.domain.similarity import is_distinct, overlap_fraction

# Roughly 111 km per degree; these routes run east along latitude 40.
STRAIGHT = [LatLon(40, -100), LatLon(40, -99)]
DENSE_STRAIGHT = [LatLon(40, -100 + i / 100) for i in range(101)]
PARALLEL_FAR = [LatLon(40.5, -100), LatLon(40.5, -99)]  # ~55 km north
NEARBY = [LatLon(40.001, -100), LatLon(40.001, -99)]  # ~110 m north
HALF = [LatLon(40, -100), LatLon(40, -99.5)]
DETOUR = [
    LatLon(40, -100),
    LatLon(40, -99.75),
    LatLon(40.4, -99.5),
    LatLon(40, -99.25),
    LatLon(40, -99),
]


def test_identical_routes_fully_overlap() -> None:
    assert overlap_fraction(STRAIGHT, STRAIGHT) == pytest.approx(1)


def test_sparse_and_dense_versions_of_same_road_overlap() -> None:
    # Two-point polyline vs 101-point polyline of the same straight road.
    assert overlap_fraction(STRAIGHT, DENSE_STRAIGHT) == pytest.approx(1)
    assert overlap_fraction(DENSE_STRAIGHT, STRAIGHT) == pytest.approx(1)


def test_small_offset_within_tolerance_still_overlaps() -> None:
    assert overlap_fraction(NEARBY, STRAIGHT) == pytest.approx(1)


def test_distant_parallel_route_does_not_overlap() -> None:
    assert overlap_fraction(PARALLEL_FAR, STRAIGHT) == 0


def test_partial_overlap_is_length_weighted() -> None:
    assert overlap_fraction(STRAIGHT, HALF) == pytest.approx(0.5, abs=0.01)
    assert overlap_fraction(HALF, STRAIGHT) == pytest.approx(1)


def test_detour_shares_only_its_common_ends() -> None:
    fraction = overlap_fraction(DETOUR, STRAIGHT)

    assert 0.3 < fraction < 0.6


def test_degenerate_route_counts_as_fully_overlapping() -> None:
    assert overlap_fraction([LatLon(40, -100)], STRAIGHT) == 1
    assert overlap_fraction([LatLon(40, -100), LatLon(40, -100)], STRAIGHT) == 1


class TestIsDistinct:
    def test_first_route_is_always_distinct(self) -> None:
        assert is_distinct(STRAIGHT, [])

    def test_duplicate_is_rejected(self) -> None:
        assert not is_distinct(DENSE_STRAIGHT, [STRAIGHT])

    def test_subset_is_rejected_in_either_direction(self) -> None:
        # HALF lies entirely on STRAIGHT, even though STRAIGHT is only half on HALF.
        assert not is_distinct(HALF, [STRAIGHT])
        assert not is_distinct(STRAIGHT, [HALF])

    def test_genuine_alternative_is_accepted(self) -> None:
        assert is_distinct(DETOUR, [STRAIGHT])
        assert is_distinct(PARALLEL_FAR, [STRAIGHT, DETOUR])

    def test_must_differ_from_every_existing_route(self) -> None:
        assert not is_distinct(DENSE_STRAIGHT, [PARALLEL_FAR, STRAIGHT])
