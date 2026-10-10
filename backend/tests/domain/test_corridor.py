from itertools import pairwise

import pytest

from trips.domain.corridor import corridor_points
from trips.domain.geo import LatLon, haversine_m

SHORT = [LatLon(40, -100), LatLon(40, -99)]  # ~85 km
CROSS_COUNTRY = [LatLon(34, -118), LatLon(39, -105), LatLon(41.9, -87.6), LatLon(40.7, -74)]


def nearest_route_distance_m(point: LatLon, route: list[LatLon]) -> float:
    # Dense sampling is accurate enough for assertions.
    samples = [
        LatLon(a.lat + (b.lat - a.lat) * t / 200, a.lon + (b.lon - a.lon) * t / 200)
        for a, b in pairwise(route)
        for t in range(201)
    ]
    return min(haversine_m(point, s) for s in samples)


def test_points_cover_the_route_within_the_buffer() -> None:
    points = corridor_points([SHORT], buffer_m=20_000, max_points=1_000)

    assert points
    # Every grid point is near the route (buffer plus one cell of rounding).
    assert max(nearest_route_distance_m(p, SHORT) for p in points) < 20_000 + 10_000
    # Every stretch of the route has grid points nearby.
    for t in range(11):
        on_route = LatLon(40, -100 + t / 10)
        assert min(haversine_m(on_route, p) for p in points) < 10_000


def test_corridor_extends_to_both_sides() -> None:
    points = corridor_points([SHORT], buffer_m=20_000, max_points=1_000)

    assert any(p.lat > 40.1 for p in points)
    assert any(p.lat < 39.9 for p in points)


def test_point_budget_is_respected_by_coarsening() -> None:
    fine = corridor_points([SHORT], buffer_m=40_000, max_points=10_000)
    capped = corridor_points([CROSS_COUNTRY], buffer_m=40_000, max_points=250)

    assert len(capped) <= 250
    assert len(capped) > 100  # the budget is used, not wasted
    assert len(fine) > 50


def test_overlapping_routes_share_points() -> None:
    single = corridor_points([SHORT], max_points=10_000)
    doubled = corridor_points([SHORT, list(reversed(SHORT))], max_points=10_000)

    assert doubled == single


def test_output_is_deterministic() -> None:
    assert corridor_points([CROSS_COUNTRY]) == corridor_points([CROSS_COUNTRY])


def test_no_routes_means_no_points() -> None:
    assert corridor_points([]) == []
    assert corridor_points([[]]) == []


@pytest.mark.parametrize(("buffer_m", "max_points"), [(0, 10), (100, 0)])
def test_invalid_parameters(buffer_m: float, max_points: int) -> None:
    with pytest.raises(ValueError, match="positive"):
        corridor_points([SHORT], buffer_m=buffer_m, max_points=max_points)
