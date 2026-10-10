from typing import ClassVar

import pytest

from trips.domain.geo import (
    LatLon,
    cumulative_distances_m,
    haversine_m,
    meters_to_miles,
    miles_to_meters,
    point_at_distance,
)

DENVER = LatLon(39.7392, -104.9903)
CHICAGO = LatLon(41.8781, -87.6298)

# One degree of latitude is ~111.2 km everywhere on the sphere.
ONE_DEGREE_LAT_M = 111_195.0


def test_mile_conversions_round_trip() -> None:
    assert miles_to_meters(1) == pytest.approx(1609.344)
    assert meters_to_miles(miles_to_meters(25)) == pytest.approx(25)


def test_haversine_zero_for_same_point() -> None:
    assert haversine_m(DENVER, DENVER) == 0


def test_haversine_one_degree_of_latitude() -> None:
    assert haversine_m(LatLon(0, 0), LatLon(1, 0)) == pytest.approx(ONE_DEGREE_LAT_M, rel=1e-3)


def test_haversine_known_city_distance_is_symmetric() -> None:
    # Denver -> Chicago great-circle distance is ~1,474 km.
    assert haversine_m(DENVER, CHICAGO) == pytest.approx(1_474_000, rel=0.01)
    assert haversine_m(DENVER, CHICAGO) == pytest.approx(haversine_m(CHICAGO, DENVER))


def test_cumulative_distances_are_monotonic_and_start_at_zero() -> None:
    points = [LatLon(0, 0), LatLon(1, 0), LatLon(1, 0), LatLon(2, 0)]

    distances = cumulative_distances_m(points)

    assert distances[0] == 0
    assert distances == sorted(distances)
    assert distances[-1] == pytest.approx(2 * ONE_DEGREE_LAT_M, rel=1e-3)


def test_cumulative_distances_single_point() -> None:
    assert cumulative_distances_m([DENVER]) == [0.0]


def test_cumulative_distances_rejects_empty_polyline() -> None:
    with pytest.raises(ValueError, match="at least one point"):
        cumulative_distances_m([])


class TestPointAtDistance:
    points: ClassVar[list[LatLon]] = [LatLon(0, 0), LatLon(1, 0), LatLon(2, 0)]
    cumulative: ClassVar[list[float]] = cumulative_distances_m(points)

    def test_interpolates_within_a_segment(self) -> None:
        point = point_at_distance(self.points, self.cumulative, self.cumulative[1] / 2)

        assert point.lat == pytest.approx(0.5)
        assert point.lon == 0

    def test_exact_vertex(self) -> None:
        assert point_at_distance(self.points, self.cumulative, self.cumulative[1]) == LatLon(1, 0)

    def test_clamps_to_start_and_end(self) -> None:
        assert point_at_distance(self.points, self.cumulative, -5) == self.points[0]
        assert point_at_distance(self.points, self.cumulative, 1e12) == self.points[-1]

    def test_skips_zero_length_segments(self) -> None:
        points = [LatLon(0, 0), LatLon(1, 0), LatLon(1, 0), LatLon(2, 0)]
        cumulative = cumulative_distances_m(points)

        point = point_at_distance(points, cumulative, cumulative[1])

        assert point == LatLon(1, 0)

    def test_rejects_mismatched_inputs(self) -> None:
        with pytest.raises(ValueError, match="same length"):
            point_at_distance(self.points, [0.0], 10)
