import pytest
import respx

from trips.domain.geo import LatLon
from trips.providers.base import Place
from trips.providers.http import ProviderError
from trips.providers.tomtom import TomTomGeocoder

SEARCH = "https://api.tomtom.com/search/2/search/"


@pytest.fixture
def geocoder() -> TomTomGeocoder:
    return TomTomGeocoder("test-key")


@respx.mock
def test_parses_places_and_sends_expected_params(geocoder: TomTomGeocoder) -> None:
    route = respx.get(url__startswith=SEARCH).respond(
        json={
            "results": [
                {
                    "position": {"lat": 39.7392, "lon": -104.9903},
                    "address": {"freeformAddress": "Denver, CO"},
                },
                {
                    "position": {"lat": 41.97, "lon": -87.9},
                    "address": {"freeformAddress": "10000 W O'Hare Ave, Chicago, IL 60666"},
                    "poi": {"name": "O'Hare International Airport"},
                },
            ]
        }
    )

    places = geocoder.search("  Denver  ", limit=3)

    assert places == [
        Place("Denver, CO", LatLon(39.7392, -104.9903)),
        Place(
            "O'Hare International Airport, 10000 W O'Hare Ave, Chicago, IL 60666",
            LatLon(41.97, -87.9),
        ),
    ]
    request = route.calls.last.request
    assert request.url.path == "/search/2/search/Denver.json"
    assert request.url.params["limit"] == "3"
    assert request.url.params["countrySet"] == "US,CA"
    assert request.url.params["typeahead"] == "true"


@respx.mock
def test_query_is_url_encoded_into_the_path(geocoder: TomTomGeocoder) -> None:
    route = respx.get(url__startswith=SEARCH).respond(json={"results": []})

    geocoder.search("I-80/Exit 5 & Main")

    assert route.calls.last.request.url.raw_path.startswith(
        b"/search/2/search/I-80%2FExit%205%20%26%20Main.json"
    )


def test_blank_query_returns_nothing_without_calling_api(geocoder: TomTomGeocoder) -> None:
    assert geocoder.search("   ") == []


@respx.mock
def test_results_without_position_are_skipped(geocoder: TomTomGeocoder) -> None:
    respx.get(url__startswith=SEARCH).respond(
        json={"results": [{"address": {"freeformAddress": "Nowhere"}}]}
    )

    assert geocoder.search("nowhere") == []


@respx.mock
def test_label_falls_back_to_coordinates(geocoder: TomTomGeocoder) -> None:
    respx.get(url__startswith=SEARCH).respond(
        json={"results": [{"position": {"lat": 40.5, "lon": -100.25}}]}
    )

    assert geocoder.search("x")[0].label == "40.5000, -100.2500"


@respx.mock
@pytest.mark.parametrize(
    "body",
    [
        {"unexpected": True},
        [],
        {"results": [{"position": {"lat": "north", "lon": 1}}]},
    ],
)
def test_malformed_responses_raise_provider_error(geocoder: TomTomGeocoder, body: object) -> None:
    respx.get(url__startswith=SEARCH).respond(json=body)

    with pytest.raises(ProviderError, match="unexpected shape"):
        geocoder.search("denver")


def test_requires_api_key() -> None:
    with pytest.raises(ValueError, match="API key"):
        TomTomGeocoder("")
