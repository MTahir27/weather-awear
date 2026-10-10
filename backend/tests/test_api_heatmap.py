from datetime import timedelta
from typing import Any

import pytest
from django.test import Client
from django.utils import timezone

from tests.services.test_plan_trip import weather
from trips.api import dependencies, views
from trips.domain.geo import LatLon
from trips.domain.polyline import encode
from trips.providers.http import ProviderUnavailable
from trips.services.heatmap import HeatmapBuilder, HeatmapRequest

URL = "/api/trips/heatmap"
ROUTE = encode([LatLon(40, -100), LatLon(40, -99)])


@pytest.fixture
def builder(monkeypatch: pytest.MonkeyPatch) -> HeatmapBuilder:
    instance = HeatmapBuilder(weather())
    monkeypatch.setattr(dependencies, "get_heatmap_builder", lambda: instance)
    return instance


def payload(**overrides: Any) -> dict[str, Any]:
    return {
        "routes": [ROUTE],
        "departure_time": (timezone.now() + timedelta(hours=1)).isoformat(),
        "load_weight_lb": 35_000,
    } | overrides


def post(client: Client, body: dict[str, Any]) -> Any:
    return client.post(URL, body, content_type="application/json")


def test_returns_column_oriented_frames(client: Client, builder: HeatmapBuilder) -> None:
    response = post(client, payload())

    assert response.status_code == 200
    body = response.json()
    points = len(body["lat"])
    assert points > 0
    assert len(body["lon"]) == points
    assert body["frame_hours"] == 1
    assert body["departure_time"].endswith("Z")
    for key in ("risk", "wind_mph", "rain_in_per_hr", "snow_in_per_hr"):
        assert len(body[key]) == 49
        assert all(len(frame) == points for frame in body[key])
    assert set(body["risk"][0]) == {0}
    assert body["wind_mph"][0][0] == 5.0


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"routes": []}, "routes"),
        ({"routes": [ROUTE] * 4}, "routes"),
        ({"routes": ["_p~iF~ps|"]}, "routes"),
        ({"routes": [encode([LatLon(40, -100)])]}, "routes"),
        ({"routes": ["x" * 50_001]}, "routes"),
        ({"departure_time": "2020-01-01T00:00:00Z"}, "departure_time"),
        ({"load_weight_lb": -5}, "load_weight_lb"),
    ],
)
def test_invalid_requests_are_rejected(
    client: Client, builder: HeatmapBuilder, overrides: dict[str, Any], field: str
) -> None:
    response = post(client, payload(**overrides))

    assert response.status_code == 400
    assert field in response.json()


def test_request_is_mapped_to_the_builder(client: Client, monkeypatch: pytest.MonkeyPatch) -> None:
    received: list[HeatmapRequest] = []

    class Recording(HeatmapBuilder):
        def build(self, request: HeatmapRequest) -> Any:
            received.append(request)
            return super().build(request)

    monkeypatch.setattr(dependencies, "get_heatmap_builder", lambda: Recording(weather()))

    post(client, payload(load_weight_lb=41_000))

    assert received[0].load_lb == 41_000
    assert received[0].routes == [[LatLon(40, -100), LatLon(40, -99)]]


def test_weather_outage_is_reported(client: Client, monkeypatch: pytest.MonkeyPatch) -> None:
    class Failing:
        def build(self, request: HeatmapRequest) -> Any:
            raise ProviderUnavailable("Open-Meteo", "timeout")

    monkeypatch.setattr(dependencies, "get_heatmap_builder", lambda: Failing())

    response = post(client, payload())

    assert response.status_code == 503
    assert response.json()["detail"].startswith("Open-Meteo is not responding")


def test_heatmap_is_rate_limited(
    client: Client, builder: HeatmapBuilder, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(views.HeatmapThrottle, "THROTTLE_RATES", {"heatmap": "1/min"})

    assert [post(client, payload()).status_code for _ in range(2)] == [200, 429]


def test_real_builder_is_constructed() -> None:
    assert isinstance(dependencies.get_heatmap_builder(), HeatmapBuilder)
