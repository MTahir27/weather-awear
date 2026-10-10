import re
from datetime import timedelta
from typing import Any

import pytest
from django.test import Client, override_settings
from django.utils import timezone

from tests.services.fakes import FakeRouter, FakeWeather, straight_route
from tests.services.test_plan_trip import weather
from trips.api import dependencies, views
from trips.domain.geo import LatLon
from trips.providers.base import NoRouteFound, ProviderRoute
from trips.providers.http import ProviderError, ProviderUnavailable
from trips.services.plan_trip import TripPlanner, TripRequest

URL = "/api/trips/plan"
ORIGIN = LatLon(40, -100)
DESTINATION = LatLon(40, -95)
ROUTES = [
    straight_route([ORIGIN, LatLon(40.6, -97.5), DESTINATION]),
    straight_route([ORIGIN, DESTINATION]),
]


class RecordingPlanner(TripPlanner):
    def __init__(self, routes: list[ProviderRoute], fake_weather: FakeWeather) -> None:
        super().__init__(FakeRouter(routes), fake_weather)
        self.requests: list[TripRequest] = []

    def plan(self, request: TripRequest) -> Any:
        self.requests.append(request)
        return super().plan(request)


@pytest.fixture
def planner(monkeypatch: pytest.MonkeyPatch) -> RecordingPlanner:
    instance = RecordingPlanner(ROUTES, weather())
    monkeypatch.setattr(dependencies, "get_trip_planner", lambda: instance)
    return instance


def payload(**overrides: Any) -> dict[str, Any]:
    return {
        "origin": {"lat": ORIGIN.lat, "lon": ORIGIN.lon, "label": "Origin"},
        "destination": {"lat": DESTINATION.lat, "lon": DESTINATION.lon, "label": "Destination"},
        "departure_time": (timezone.now() + timedelta(hours=2)).isoformat(),
        "load_weight_lb": 32_000,
        "sample_interval_mi": 25,
        "hours_of_service": True,
    } | overrides


def post(client: Client, body: dict[str, Any]) -> Any:
    return client.post(URL, body, content_type="application/json")


def test_plan_returns_ranked_routes_with_checkpoints(
    client: Client, planner: RecordingPlanner
) -> None:
    response = post(client, payload())

    assert response.status_code == 200
    body = response.json()
    assert body["sample_interval_mi"] == 25
    assert body["load_weight_lb"] == 32_000
    assert body["recommendation"]["route_id"] == "route-2"
    assert body["recommendation"]["travel_advised"] is True
    assert body["recommendation"]["explanation"]

    routes = body["routes"]
    assert [r["rank"] for r in routes] == [1, 2]
    assert [r["recommended"] for r in routes] == [True, False]
    best = routes[0]
    assert best["id"] == "route-2"
    assert isinstance(best["geometry"], str)
    assert best["geometry"]
    assert best["distance_mi"] == pytest.approx(265.4, abs=1)
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", best["arrival_time"])
    assert set(best["risk"]["miles_by_level"]) == {"low", "moderate", "high", "severe", "no_travel"}
    assert best["risk"]["worst_level"] == "low"

    checkpoint = best["checkpoints"][1]
    assert checkpoint["mile"] == 25
    assert checkpoint["level"] == "low"
    assert set(checkpoint) == {
        "mile",
        "lat",
        "lon",
        "eta",
        "level",
        "wind_mph",
        "gust_mph",
        "rain_in_per_hr",
        "snow_in_per_hr",
        "drivers",
        "load_escalated",
    }
    assert best["stops"] == []


def test_request_is_mapped_to_the_planner(client: Client, planner: RecordingPlanner) -> None:
    post(client, payload(sample_interval_mi=10, hours_of_service=False, load_weight_lb=45_500))

    request = planner.requests[0]
    assert request.origin == ORIGIN
    assert request.destination == DESTINATION
    assert request.interval_mi == 10
    assert request.enforce_hos is False
    assert request.load_lb == 45_500


def test_defaults_for_optional_fields(client: Client, planner: RecordingPlanner) -> None:
    body = payload()
    del body["sample_interval_mi"], body["hours_of_service"]

    post(client, body)

    assert planner.requests[0].interval_mi == 25
    assert planner.requests[0].enforce_hos is True


def test_departure_moments_ago_is_treated_as_now(client: Client, planner: RecordingPlanner) -> None:
    post(client, payload(departure_time=(timezone.now() - timedelta(minutes=5)).isoformat()))

    assert planner.requests[0].depart_at >= timezone.now() - timedelta(seconds=5)


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"departure_time": "2020-01-01T00:00:00Z"}, "departure_time"),
        ({"departure_time": "not-a-date"}, "departure_time"),
        ({"load_weight_lb": -1}, "load_weight_lb"),
        ({"load_weight_lb": 150_001}, "load_weight_lb"),
        ({"load_weight_lb": "heavy"}, "load_weight_lb"),
        ({"sample_interval_mi": 30}, "sample_interval_mi"),
        ({"origin": {"lat": 91, "lon": 0}}, "origin"),
        ({"destination": {"lat": 40, "lon": -181}}, "destination"),
        ({"origin": None}, "origin"),
    ],
)
def test_invalid_input_is_rejected(
    client: Client, planner: RecordingPlanner, overrides: dict[str, Any], field: str
) -> None:
    response = post(client, payload(**overrides))

    assert response.status_code == 400
    assert field in response.json()
    assert planner.requests == []


def test_departure_more_than_a_week_ahead_is_rejected(
    client: Client, planner: RecordingPlanner
) -> None:
    response = post(
        client, payload(departure_time=(timezone.now() + timedelta(days=8)).isoformat())
    )

    assert response.status_code == 400
    assert "7 days" in response.json()["departure_time"][0]


def test_origin_and_destination_must_differ(client: Client, planner: RecordingPlanner) -> None:
    response = post(client, payload(destination={"lat": 40.001, "lon": -100.001}))

    assert response.status_code == 400
    assert "at least 1 mile" in response.json()["destination"][0]


def test_rejects_non_json_and_get(client: Client) -> None:
    assert (
        client.post(URL, "a=b", content_type="application/x-www-form-urlencoded").status_code == 415
    )
    assert client.get(URL).status_code == 405


class FailingPlanner:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def plan(self, request: TripRequest) -> Any:
        raise self.error


@pytest.mark.parametrize(
    ("error", "status", "detail"),
    [
        (NoRouteFound("ocean"), 422, "No truck route connects these locations."),
        (ProviderUnavailable("TomTom", "timeout"), 503, "TomTom is not responding"),
        (ProviderError("Open-Meteo", "bad shape"), 502, "Open-Meteo returned an unexpected"),
    ],
)
def test_provider_failures_map_to_clear_errors(
    client: Client,
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    status: int,
    detail: str,
) -> None:
    monkeypatch.setattr(dependencies, "get_trip_planner", lambda: FailingPlanner(error))

    response = post(client, payload())

    assert response.status_code == status
    assert response.json()["detail"].startswith(detail)


@override_settings(TOMTOM_API_KEY="")
def test_missing_api_key_is_a_service_unavailable_error(client: Client) -> None:
    response = post(client, payload())

    assert response.status_code == 503
    assert response.json() == {"detail": "The routing service is not configured."}


def test_real_planner_is_built_from_settings() -> None:
    assert isinstance(dependencies.get_trip_planner(), TripPlanner)
    assert dependencies.get_trip_planner() is dependencies.get_trip_planner()


def test_planning_is_rate_limited(
    client: Client, planner: RecordingPlanner, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(views.PlanThrottle, "THROTTLE_RATES", {"plan": "2/min"})

    statuses = [post(client, payload()).status_code for _ in range(3)]

    assert statuses == [200, 200, 429]


def test_long_trip_reports_hours_of_service_stops(
    client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    far = LatLon(40, -80)  # ~19 h of driving
    instance = RecordingPlanner([straight_route([ORIGIN, far])], weather())
    monkeypatch.setattr(dependencies, "get_trip_planner", lambda: instance)

    response = post(client, payload(destination={"lat": far.lat, "lon": far.lon}))

    stops = response.json()["routes"][0]["stops"]
    assert [s["kind"] for s in stops] == ["break", "rest"]
    assert set(stops[1]) == {"kind", "mile", "lat", "lon", "starts_at", "ends_at"}
    assert stops[1]["starts_at"] < stops[1]["ends_at"]
