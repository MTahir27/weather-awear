from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import respx

from trips.domain.geo import LatLon
from trips.providers.base import Avoid, NoRouteFound
from trips.providers.http import ProviderError
from trips.providers.tomtom import TomTomRouter

ROUTING = "https://api.tomtom.com/routing/1/calculateRoute/"
DENVER = LatLon(39.7392, -104.9903)
CHICAGO = LatLon(41.8781, -87.6298)
OMAHA = LatLon(41.2565, -95.9345)


def future(hours: float = 2) -> datetime:
    return datetime.now(UTC) + timedelta(hours=hours)


def tomtom_route(
    legs: list[list[tuple[float, float]]],
    *,
    length: float = 1_000,
    time: float = 60,
    progress: list[tuple[int, float, float]] | None = None,
) -> dict[str, Any]:
    route: dict[str, Any] = {
        "summary": {
            "lengthInMeters": length,
            "travelTimeInSeconds": time,
            "trafficDelayInSeconds": 5,
        },
        "legs": [{"points": [{"latitude": a, "longitude": b} for a, b in leg]} for leg in legs],
    }
    if progress is not None:
        route["progress"] = [
            {"pointIndex": i, "distanceInMeters": d, "travelTimeInSeconds": t}
            for i, d, t in progress
        ]
    return route


@pytest.fixture
def router() -> TomTomRouter:
    return TomTomRouter("test-key")


@respx.mock
def test_requests_traffic_aware_truck_routes(router: TomTomRouter) -> None:
    depart = datetime(2030, 1, 15, 8, 30, tzinfo=UTC)
    api = respx.get(url__startswith=ROUTING).respond(
        json={"routes": [tomtom_route([[(0, 0), (0, 1)]], progress=[(0, 0, 0), (1, 1000, 60)])]}
    )

    router.truck_routes(
        DENVER, CHICAGO, depart_at=depart, gross_weight_kg=20_000, max_alternatives=2
    )

    request = api.calls.last.request
    assert request.url.path == (
        "/routing/1/calculateRoute/39.739200,-104.990300:41.878100,-87.629800/json"
    )
    params = request.url.params
    assert params["travelMode"] == "truck"
    assert params["vehicleCommercial"] == "true"
    assert params["vehicleWeight"] == "20000"
    assert params["traffic"] == "true"
    assert params["departAt"] == "2030-01-15T08:30:00Z"
    assert params["maxAlternatives"] == "2"
    assert params.get_list("extendedRouteRepresentation") == ["distance", "travelTime"]
    assert "avoid" not in params


@respx.mock
def test_parses_routes_in_provider_order(router: TomTomRouter) -> None:
    respx.get(url__startswith=ROUTING).respond(
        json={
            "routes": [
                tomtom_route(
                    [[(39.7, -104.9), (40.0, -100.0), (41.8, -87.6)]],
                    length=1_600_000,
                    time=50_000,
                    progress=[(0, 0, 0), (1, 700_000, 22_000), (2, 1_600_000, 50_000)],
                ),
                tomtom_route([[(39.7, -104.9), (41.8, -87.6)]], length=1_700_000, time=55_000),
            ]
        }
    )

    routes = router.truck_routes(DENVER, CHICAGO, depart_at=future(), gross_weight_kg=20_000)

    assert len(routes) == 2
    best = routes[0]
    assert best.points == (LatLon(39.7, -104.9), LatLon(40.0, -100.0), LatLon(41.8, -87.6))
    assert best.length_m == 1_600_000
    assert best.travel_time_s == 50_000
    assert best.traffic_delay_s == 5
    assert best.progress == ((0, 0), (700_000, 22_000), (1_600_000, 50_000))


@respx.mock
def test_missing_progress_falls_back_to_start_and_end_anchors(router: TomTomRouter) -> None:
    respx.get(url__startswith=ROUTING).respond(
        json={"routes": [tomtom_route([[(0, 0), (0, 1)]], length=5_000, time=300)]}
    )

    route = router.truck_routes(DENVER, CHICAGO, depart_at=future(), gross_weight_kg=1)[0]

    assert route.progress == ((0, 0), (5_000, 300))


@respx.mock
def test_progress_is_extended_to_cover_whole_route(router: TomTomRouter) -> None:
    respx.get(url__startswith=ROUTING).respond(
        json={
            "routes": [
                tomtom_route([[(0, 0), (0, 1)]], length=5_000, time=300, progress=[(1, 2_000, 100)])
            ]
        }
    )

    route = router.truck_routes(DENVER, CHICAGO, depart_at=future(), gross_weight_kg=1)[0]

    assert route.progress == ((0, 0), (2_000, 100), (5_000, 300))


@respx.mock
def test_via_points_and_avoid_options(router: TomTomRouter) -> None:
    api = respx.get(url__startswith=ROUTING).respond(
        json={"routes": [tomtom_route([[(0, 0), (1, 1)], [(1, 1), (2, 2)]])]}
    )

    route = router.truck_routes(
        DENVER,
        CHICAGO,
        depart_at=future(),
        gross_weight_kg=1,
        max_alternatives=2,
        via=[OMAHA],
        avoid=[Avoid.MOTORWAYS, Avoid.TOLL_ROADS],
    )[0]

    request = api.calls.last.request
    assert ":41.256500,-95.934500:" in request.url.path
    assert request.url.params["maxAlternatives"] == "0"
    assert request.url.params.get_list("avoid") == ["motorways", "tollRoads"]
    # Legs are concatenated as-is; TomTom's progress indexes include the shared point.
    assert route.points == (LatLon(0, 0), LatLon(1, 1), LatLon(1, 1), LatLon(2, 2))


@respx.mock
def test_departure_now_or_past_is_sent_as_now(router: TomTomRouter) -> None:
    api = respx.get(url__startswith=ROUTING).respond(json={"routes": [tomtom_route([[(0, 0)]])]})

    router.truck_routes(
        DENVER, CHICAGO, depart_at=datetime.now(UTC) - timedelta(minutes=5), gross_weight_kg=1
    )

    assert api.calls.last.request.url.params["departAt"] == "now"


def test_naive_departure_is_rejected(router: TomTomRouter) -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        router.truck_routes(DENVER, CHICAGO, depart_at=datetime(2030, 1, 1), gross_weight_kg=1)


@respx.mock
@pytest.mark.parametrize("code", ["NO_ROUTE_FOUND", "MAP_MATCHING_FAILURE"])
def test_unroutable_request_raises_no_route_found(router: TomTomRouter, code: str) -> None:
    respx.get(url__startswith=ROUTING).respond(
        400, json={"detailedError": {"message": "Engine error", "code": code}}
    )

    with pytest.raises(NoRouteFound):
        router.truck_routes(DENVER, LatLon(51.5, -0.12), depart_at=future(), gross_weight_kg=1)


@respx.mock
def test_empty_route_list_raises_no_route_found(router: TomTomRouter) -> None:
    respx.get(url__startswith=ROUTING).respond(json={"routes": []})

    with pytest.raises(NoRouteFound):
        router.truck_routes(DENVER, CHICAGO, depart_at=future(), gross_weight_kg=1)


@respx.mock
@pytest.mark.parametrize(
    "payload",
    [{"detailedError": {"code": "BAD_INPUT"}}, {"detailedError": {"code": 7}}, {"error": "x"}],
)
def test_other_client_errors_propagate(router: TomTomRouter, payload: dict[str, Any]) -> None:
    respx.get(url__startswith=ROUTING).respond(400, json=payload)

    with pytest.raises(ProviderError) as excinfo:
        router.truck_routes(DENVER, CHICAGO, depart_at=future(), gross_weight_kg=1)

    assert not isinstance(excinfo.value, NoRouteFound)


@respx.mock
@pytest.mark.parametrize(
    ("body", "message"),
    [
        ({"nope": []}, "unexpected shape"),
        ({"routes": [{"legs": []}]}, "unexpected shape"),
        ({"routes": [tomtom_route([[]])]}, "no geometry"),
    ],
)
def test_malformed_routes_raise_provider_error(
    router: TomTomRouter, body: dict[str, Any], message: str
) -> None:
    respx.get(url__startswith=ROUTING).respond(json=body)

    with pytest.raises(ProviderError, match=message):
        router.truck_routes(DENVER, CHICAGO, depart_at=future(), gross_weight_kg=1)


def test_requires_api_key() -> None:
    with pytest.raises(ValueError, match="API key"):
        TomTomRouter("")
