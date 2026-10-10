from collections.abc import Callable
from datetime import UTC, datetime

import pytest

from tests.services.fakes import FakeRouter, RouterCall, straight_route
from trips.domain.geo import LatLon, haversine_m, initial_bearing_deg
from trips.providers.base import Avoid, NoRouteFound, ProviderRoute
from trips.providers.http import ProviderError, ProviderUnavailable
from trips.services.route_options import (
    RouteQuery,
    collect_route_options,
    via_points,
)

ORIGIN = LatLon(40, -100)
DESTINATION = LatLon(40, -99)
QUERY = RouteQuery(ORIGIN, DESTINATION, datetime(2030, 1, 1, tzinfo=UTC), 30_000)

MAIN = straight_route([ORIGIN, DESTINATION])
DUPLICATE = straight_route([LatLon(40, -100 + i / 20) for i in range(21)])
NORTH = straight_route([ORIGIN, LatLon(40.3, -99.5), DESTINATION])
SOUTH = straight_route([ORIGIN, LatLon(39.7, -99.5), DESTINATION])
TOLL_FREE = straight_route([ORIGIN, LatLon(40.15, -99.5), DESTINATION])
HUGE_DETOUR = straight_route([ORIGIN, LatLon(41.5, -99.5), DESTINATION], speed_mps=10)


def by_call(
    north: list[ProviderRoute] | None = None,
    south: list[ProviderRoute] | None = None,
    tolls: list[ProviderRoute] | None = None,
    motorways: list[ProviderRoute] | None = None,
) -> Callable[[RouterCall], list[ProviderRoute]]:
    def respond(call: RouterCall) -> list[ProviderRoute]:
        if call.via:
            return (north if call.via[0].lat > 40 else south) or []
        if call.avoid == (Avoid.TOLL_ROADS,):
            return tolls or []
        return motorways or []

    return respond


def test_three_provider_routes_are_used_as_is() -> None:
    router = FakeRouter([MAIN, NORTH, SOUTH], respond=by_call(tolls=[TOLL_FREE]))

    routes = collect_route_options(router, QUERY)

    assert routes == [MAIN, NORTH, SOUTH]
    main_call = next(c for c in router.calls if not c.via and not c.avoid)
    assert main_call.max_alternatives == 2
    assert main_call.gross_weight_kg == 30_000


def test_fills_missing_alternatives_from_fallbacks_in_preference_order() -> None:
    router = FakeRouter([MAIN], respond=by_call(north=[NORTH], south=[SOUTH], tolls=[TOLL_FREE]))

    routes = collect_route_options(router, QUERY)

    assert routes == [MAIN, NORTH, SOUTH]
    fallback_calls = router.calls[1:]
    assert len(fallback_calls) == 4
    assert {c.avoid for c in fallback_calls} == {(), (Avoid.TOLL_ROADS,), (Avoid.MOTORWAYS,)}


def test_duplicate_provider_alternatives_are_removed_and_replaced() -> None:
    router = FakeRouter([MAIN, DUPLICATE], respond=by_call(north=[NORTH], south=[SOUTH]))

    assert collect_route_options(router, QUERY) == [MAIN, NORTH, SOUTH]


def test_duplicate_and_excessive_detour_fallbacks_are_skipped() -> None:
    router = FakeRouter(
        [MAIN],
        respond=by_call(north=[HUGE_DETOUR], south=[DUPLICATE], tolls=[TOLL_FREE]),
    )

    assert collect_route_options(router, QUERY) == [MAIN, TOLL_FREE]


def test_failed_fallbacks_are_ignored() -> None:
    def respond(call: RouterCall) -> list[ProviderRoute]:
        if call.via:
            raise NoRouteFound("off-road via point")
        if call.avoid == (Avoid.TOLL_ROADS,):
            raise ProviderUnavailable("TomTom", "timeout")
        raise ProviderError("TomTom", "bad request")

    router = FakeRouter([MAIN, NORTH], respond=respond)

    assert collect_route_options(router, QUERY) == [MAIN, NORTH]


def test_no_route_from_main_request_propagates() -> None:
    class Unroutable(FakeRouter):
        def truck_routes(self, *args: object, **kwargs: object) -> list[ProviderRoute]:
            raise NoRouteFound("ocean")

    with pytest.raises(NoRouteFound):
        collect_route_options(Unroutable([]), QUERY)


def test_fallbacks_are_requested_alongside_the_main_request() -> None:
    router = FakeRouter([MAIN, NORTH, SOUTH])

    collect_route_options(router, QUERY)

    # One main request plus four concurrent fallbacks, regardless of the outcome.
    assert len(router.calls) == 5
    assert all(c.max_alternatives == 0 for c in router.calls if c.via or c.avoid)


def test_via_points_sit_either_side_of_the_trip_midpoint() -> None:
    left, right = via_points(ORIGIN, DESTINATION)
    midpoint = LatLon(40.0, -99.5)
    # ~85 km apart, so 15% would be under the 15 km minimum offset.
    expected_offset = max(0.15 * haversine_m(ORIGIN, DESTINATION), 15_000)

    for point in (left, right):
        assert haversine_m(midpoint, point) == pytest.approx(expected_offset, rel=0.01)
    assert left.lat > 40 > right.lat  # heading east: left is north
    bearing = initial_bearing_deg(midpoint, left)
    assert min(bearing, 360 - bearing) < 1  # due north, allowing for wrap-around


@pytest.mark.parametrize(
    ("destination", "expected_offset_m"),
    [(LatLon(40, -99.9), 15_000), (LatLon(40, -80), 150_000)],
)
def test_via_offset_is_bounded(destination: LatLon, expected_offset_m: float) -> None:
    left, right = via_points(ORIGIN, destination)

    assert haversine_m(left, right) == pytest.approx(2 * expected_offset_m, rel=0.02)
