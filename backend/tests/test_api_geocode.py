from dataclasses import dataclass, field

import pytest
from django.test import Client, override_settings

from trips.api import dependencies
from trips.domain.geo import LatLon
from trips.providers.base import Place
from trips.providers.http import ProviderUnavailable
from trips.providers.tomtom import TomTomGeocoder

URL = "/api/geocode"


@dataclass
class FakeGeocoder:
    places: list[Place]
    queries: list[str] = field(default_factory=list)
    error: Exception | None = None

    def search(self, query: str, *, limit: int = 5) -> list[Place]:
        self.queries.append(query)
        if self.error:
            raise self.error
        return self.places[:limit]


@pytest.fixture
def geocoder(monkeypatch: pytest.MonkeyPatch) -> FakeGeocoder:
    fake = FakeGeocoder([Place("Denver, CO", LatLon(39.7392, -104.9903))])
    monkeypatch.setattr(dependencies, "get_geocoder", lambda: fake)
    return fake


def test_returns_places(client: Client, geocoder: FakeGeocoder) -> None:
    response = client.get(URL, {"q": "Denver"})

    assert response.status_code == 200
    assert response.json() == {
        "results": [{"label": "Denver, CO", "lat": 39.7392, "lon": -104.9903}]
    }


def test_results_are_cached_case_insensitively(client: Client, geocoder: FakeGeocoder) -> None:
    client.get(URL, {"q": "Denver"})
    client.get(URL, {"q": "denver "})

    assert geocoder.queries == ["Denver"]


@pytest.mark.parametrize("params", [{}, {"q": ""}, {"q": "a"}, {"q": "x" * 121}])
def test_query_is_validated(client: Client, geocoder: FakeGeocoder, params: dict[str, str]) -> None:
    response = client.get(URL, params)

    assert response.status_code == 400
    assert "q" in response.json()
    assert geocoder.queries == []


def test_provider_failure_is_reported_and_not_cached(
    client: Client, geocoder: FakeGeocoder
) -> None:
    geocoder.error = ProviderUnavailable("TomTom", "timeout")

    assert client.get(URL, {"q": "Denver"}).status_code == 503

    geocoder.error = None
    assert client.get(URL, {"q": "Denver"}).status_code == 200


@override_settings(TOMTOM_API_KEY="")
def test_missing_api_key(client: Client) -> None:
    assert client.get(URL, {"q": "Denver"}).status_code == 503


def test_real_geocoder_is_built_from_settings() -> None:
    assert isinstance(dependencies.get_geocoder(), TomTomGeocoder)


def test_geocoding_is_rate_limited(
    client: Client, geocoder: FakeGeocoder, monkeypatch: pytest.MonkeyPatch
) -> None:
    from trips.api import views

    monkeypatch.setattr(views.GeocodeThrottle, "THROTTLE_RATES", {"geocode": "2/min"})

    statuses = [client.get(URL, {"q": f"place {i}"}).status_code for i in range(3)]

    assert statuses == [200, 200, 429]
