import math
from itertools import pairwise

import pytest

from trips.domain.geo import LatLon
from trips.domain.polyline import _offset_m, decode, encode, simplify


def test_encode_matches_googles_reference_example() -> None:
    # Example from Google's polyline algorithm documentation.
    points = [LatLon(38.5, -120.2), LatLon(40.7, -120.95), LatLon(43.252, -126.453)]

    assert encode(points) == "_p~iF~ps|U_ulLnnqC_mqNvxq`@"


def test_decode_reverses_encode() -> None:
    points = [LatLon(38.5, -120.2), LatLon(40.7, -120.95), LatLon(43.252, -126.453)]

    assert decode("_p~iF~ps|U_ulLnnqC_mqNvxq`@") == points
    assert decode(encode(points)) == points
    assert decode("") == []


@pytest.mark.parametrize("bad", ["_p~iF~ps|", "_p~iF\x00\x00", "~~~~~~"])
def test_decode_rejects_malformed_input(bad: str) -> None:
    with pytest.raises(ValueError, match="Malformed"):
        decode(bad)


def test_encode_empty() -> None:
    assert encode([]) == ""


def test_encode_rounds_to_precision() -> None:
    assert encode([LatLon(38.500004, -120.199996)]) == encode([LatLon(38.5, -120.2)])


class TestSimplify:
    def test_collinear_points_collapse_to_endpoints(self) -> None:
        line = [LatLon(40, -100 + i / 100) for i in range(101)]

        assert simplify(line, 10) == [line[0], line[-1]]

    def test_significant_corner_is_kept(self) -> None:
        corner = [LatLon(40, -100), LatLon(40, -99.5), LatLon(40.5, -99.5)]

        assert simplify(corner, 10) == corner

    def test_small_wiggle_below_tolerance_is_dropped(self) -> None:
        # ~5.5 m off the straight line.
        wiggle = [LatLon(40, -100), LatLon(40.00005, -99.5), LatLon(40, -99)]

        assert simplify(wiggle, 10) == [wiggle[0], wiggle[-1]]
        assert simplify(wiggle, 1) == wiggle

    def test_every_dropped_point_stays_within_tolerance(self) -> None:
        # Gently curving, highway-like road sampled every ~170 m.
        route = [LatLon(40 + 0.05 * math.sin(i / 300), -100 + i / 500) for i in range(2_000)]
        simplified = simplify(route, 15)

        assert len(simplified) < len(route) / 5
        kept = [route.index(p) for p in simplified]
        for start, end in pairwise(kept):
            for i in range(start + 1, end):
                assert _offset_m(route[i], route[start], route[end]) <= 15 + 1e-9

    @pytest.mark.parametrize("n", [0, 1, 2])
    def test_short_inputs_are_returned_unchanged(self, n: int) -> None:
        points = [LatLon(40, -100 + i) for i in range(n)]

        assert simplify(points, 10) == points

    def test_duplicate_endpoints(self) -> None:
        loop = [LatLon(40, -100), LatLon(40.1, -100), LatLon(40, -100)]

        assert simplify(loop, 10) == loop
