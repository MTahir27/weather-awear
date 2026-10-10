from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
import respx

from trips.domain.geo import LatLon
from trips.providers import open_meteo
from trips.providers.http import ProviderError
from trips.providers.open_meteo import OpenMeteoProvider

URL = "https://api.open-meteo.com/v1/forecast"
START = datetime.now(UTC).replace(minute=20, second=0, microsecond=0) + timedelta(hours=1)
T0 = int(START.replace(minute=0).timestamp())


def location_payload(hours: int = 2, *, rain: float | None = 0.05) -> dict[str, Any]:
    return {
        "hourly": {
            "time": [T0 + i * 3600 for i in range(hours)],
            "wind_speed_10m": [10.0 + i for i in range(hours)],
            "wind_gusts_10m": [20.0 + i for i in range(hours)],
            "rain": [rain] * hours,
            "showers": [0.05] * hours,
            "snowfall": [0.0] * hours,
        }
    }


@pytest.fixture
def provider() -> OpenMeteoProvider:
    return OpenMeteoProvider()


@respx.mock
def test_requests_expected_units_window_and_locations(provider: OpenMeteoProvider) -> None:
    api = respx.get(URL).respond(json=[location_payload(), location_payload()])

    series = provider.hourly(
        [LatLon(39.73921, -104.99031), LatLon(41.8781, -87.6298)],
        START,
        START + timedelta(minutes=30),
    )

    params = api.calls.last.request.url.params
    assert params["latitude"] == "39.7392,41.8781"
    assert params["longitude"] == "-104.9903,-87.6298"
    assert params["hourly"] == "wind_speed_10m,wind_gusts_10m,rain,showers,snowfall"
    assert params["wind_speed_unit"] == "mph"
    assert params["precipitation_unit"] == "inch"
    assert params["timeformat"] == "unixtime"
    # Every location is fetched for one fixed window: the past hour to 12 days ahead.
    first = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    assert params["start_hour"] == first.strftime("%Y-%m-%dT%H:00")
    assert params["end_hour"] == (first + timedelta(days=12)).strftime("%Y-%m-%dT%H:00")
    assert len(series) == 2


@respx.mock
def test_parses_series_and_combines_rain_with_showers(provider: OpenMeteoProvider) -> None:
    respx.get(URL).respond(json=location_payload())

    series = provider.hourly([LatLon(40, -100)], START, START)[0]

    assert series.times == (T0, T0 + 3600)
    assert series.wind_mph == (10.0, 11.0)
    assert series.gust_mph == (20.0, 21.0)
    assert series.rain_in == pytest.approx((0.1, 0.1))
    assert series.snow_in == (0.0, 0.0)


@respx.mock
def test_missing_rain_keeps_total_unknown(provider: OpenMeteoProvider) -> None:
    respx.get(URL).respond(json=location_payload(rain=None))

    series = provider.hourly([LatLon(40, -100)], START, START)[0]

    assert series.rain_in == (None, None)


@respx.mock
def test_large_requests_are_batched_and_keep_input_order(
    provider: OpenMeteoProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(open_meteo, "BATCH_SIZE", 2)

    def respond(request: httpx.Request) -> httpx.Response:
        lats = request.url.params["latitude"].split(",")
        payloads = []
        for lat in lats:
            payload = location_payload()
            payload["hourly"]["wind_speed_10m"] = [float(lat)] * 2
            payloads.append(payload)
        return httpx.Response(200, json=payloads)

    api = respx.get(URL).mock(side_effect=respond)
    locations = [LatLon(float(i), -100) for i in range(5)]

    series = provider.hourly(locations, START, START)

    assert api.call_count == 3
    assert [s.wind_mph[0] for s in series] == [0, 1, 2, 3, 4]


@respx.mock
def test_window_is_capped_at_forecast_horizon(provider: OpenMeteoProvider) -> None:
    api = respx.get(URL).respond(json=location_payload())

    provider.hourly([LatLon(40, -100)], START, START + timedelta(days=30))

    end_hour = datetime.strptime(api.calls.last.request.url.params["end_hour"], "%Y-%m-%dT%H:%M")
    assert end_hour.replace(tzinfo=UTC) <= datetime.now(UTC) + timedelta(days=16)


def test_window_beyond_horizon_is_rejected(provider: OpenMeteoProvider) -> None:
    late = datetime.now(UTC) + timedelta(days=20)

    with pytest.raises(ValueError, match="beyond the forecast horizon"):
        provider.hourly([LatLon(40, -100)], late, late)


def test_no_locations_makes_no_request(provider: OpenMeteoProvider) -> None:
    assert provider.hourly([], START, START) == []


def test_naive_times_are_rejected(provider: OpenMeteoProvider) -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        provider.hourly([LatLon(40, -100)], datetime(2030, 1, 1), datetime(2030, 1, 2))


@respx.mock
def test_location_count_mismatch_is_rejected(provider: OpenMeteoProvider) -> None:
    respx.get(URL).respond(json=[location_payload()])

    with pytest.raises(ProviderError, match="different number of locations"):
        provider.hourly([LatLon(40, -100), LatLon(41, -100)], START, START)


@respx.mock
@pytest.mark.parametrize(
    "payload",
    [
        {"error": True, "reason": "bad"},
        {"hourly": {"time": [T0]}},
        {"hourly": {**location_payload()["hourly"], "showers": [0.0]}},
    ],
)
def test_malformed_forecast_raises_provider_error(
    provider: OpenMeteoProvider, payload: dict[str, Any]
) -> None:
    respx.get(URL).respond(json=payload)

    with pytest.raises(ProviderError, match="unexpected shape"):
        provider.hourly([LatLon(40, -100)], START, START)


@respx.mock
def test_repeat_requests_are_served_from_cache(provider: OpenMeteoProvider) -> None:
    api = respx.get(URL).respond(json=[location_payload(), location_payload()])
    locations = [LatLon(40, -100), LatLon(41, -100)]

    first = provider.hourly(locations, START, START)
    second = provider.hourly(list(reversed(locations)), START, START + timedelta(minutes=30))

    assert api.call_count == 1
    assert second == list(reversed(first))


@respx.mock
def test_only_missing_locations_are_fetched(provider: OpenMeteoProvider) -> None:
    api = respx.get(URL).mock(
        side_effect=[
            httpx.Response(200, json=location_payload()),
            httpx.Response(200, json=location_payload()),
        ]
    )

    provider.hourly([LatLon(40, -100)], START, START)
    provider.hourly([LatLon(40, -100), LatLon(42, -100)], START, START)

    assert api.call_count == 2
    assert api.calls.last.request.url.params["latitude"] == "42.0000"


@respx.mock
def test_duplicate_locations_are_fetched_once(provider: OpenMeteoProvider) -> None:
    api = respx.get(URL).respond(json=location_payload())

    series = provider.hourly([LatLon(40, -100), LatLon(40.00001, -100)], START, START)

    assert api.calls.last.request.url.params["latitude"] == "40.0000"
    assert series[0] is series[1]


@respx.mock
def test_cached_series_not_covering_the_request_is_refetched(
    provider: OpenMeteoProvider,
) -> None:
    # The fake series covers only two hours, so a later request is not covered.
    api = respx.get(URL).respond(json=location_payload(hours=2))

    provider.hourly([LatLon(40, -100)], START, START)
    provider.hourly([LatLon(40, -100)], START, START + timedelta(hours=5))

    assert api.call_count == 2
