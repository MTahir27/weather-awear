from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from tests.services.fakes import FakeRouter, FakeWeather, straight_route
from trips.domain.forecast import HourlySeries
from trips.domain.geo import LatLon, meters_to_miles
from trips.domain.hos import StopKind
from trips.domain.recommend import DecidingFactor
from trips.domain.risk import Factor, RiskLevel
from trips.providers.base import ProviderRoute
from trips.providers.http import ProviderError
from trips.services.plan_trip import TripPlanner, TripRequest, gross_weight_kg

HOUR = 3_600
DEPART = datetime(2030, 3, 1, 8, 0, tzinfo=UTC)
ORIGIN = LatLon(40, -100)
DESTINATION = LatLon(40, -95)  # ~427 km east; ~4.7 h at 25 m/s

DIRECT = straight_route([ORIGIN, DESTINATION])
NORTH = straight_route([ORIGIN, LatLon(40.6, -97.5), DESTINATION])
SOUTH = straight_route([ORIGIN, LatLon(39.4, -97.5), DESTINATION])

# (wind mph, rain in/hr, snow in/hr) at a location and Unix time.
Conditions = Callable[[LatLon, int], tuple[float, float, float]]


def calm(location: LatLon, t: int) -> tuple[float, float, float]:
    return (5.0, 0.0, 0.0)


def weather(conditions: Conditions = calm, hours_available: int | None = None) -> FakeWeather:
    def series_for(location: LatLon, start: datetime, end: datetime) -> HourlySeries:
        first = int(start.timestamp()) // HOUR * HOUR
        last = -(-int(end.timestamp()) // HOUR) * HOUR
        times = list(range(first, last + HOUR, HOUR))
        if hours_available is not None:
            times = times[:hours_available]
        values = [conditions(location, t) for t in times]
        return HourlySeries(
            times=tuple(times),
            wind_mph=tuple(v[0] for v in values),
            gust_mph=tuple(v[0] * 1.5 for v in values),
            rain_in=tuple(v[1] for v in values),
            snow_in=tuple(v[2] for v in values),
        )

    return FakeWeather(series_for)


BASE_REQUEST = TripRequest(
    origin=ORIGIN,
    destination=DESTINATION,
    depart_at=DEPART,
    load_lb=20_000,
    interval_mi=25,
    enforce_hos=True,
)


def request(**overrides: Any) -> TripRequest:
    return replace(BASE_REQUEST, **overrides)


def test_calm_weather_ranks_routes_by_travel_time() -> None:
    planner = TripPlanner(FakeRouter([NORTH, DIRECT, SOUTH]), weather())

    result = planner.plan(request())

    assert result.recommendation.recommended_id == "route-2"  # DIRECT is shortest/fastest
    assert result.recommendation.deciding_factor == DecidingFactor.TRAVEL_TIME
    assert result.recommendation.travel_advised
    assert result.routes[0].route_id == "route-2"
    assert all(r.risk.worst_level == RiskLevel.LOW for r in result.routes)


def test_checkpoints_every_interval_with_increasing_etas() -> None:
    result = TripPlanner(FakeRouter([DIRECT]), weather()).plan(request(interval_mi=25))
    route = result.routes[0]

    miles = [round(meters_to_miles(c.distance_m), 3) for c in route.checkpoints]
    assert miles[:3] == [0, 25, 50]
    assert miles[-1] == pytest.approx(meters_to_miles(DIRECT.length_m), abs=0.01)
    assert route.checkpoints[0].eta == DEPART
    assert [c.eta for c in route.checkpoints] == sorted(c.eta for c in route.checkpoints)
    # Constant 25 m/s: 25 miles takes 1609.344 s.
    assert route.checkpoints[1].eta == DEPART + timedelta(seconds=1_609.344)
    assert route.arrive_at == DEPART + timedelta(seconds=route.duration_s)
    assert route.checkpoints[-1].eta == route.arrive_at


def test_storm_on_one_route_changes_the_recommendation() -> None:
    def storm_north(location: LatLon, t: int) -> tuple[float, float, float]:
        return (60.0, 0.0, 0.0) if location.lat > 40.3 else (5.0, 0.0, 0.0)

    # NORTH would win on order alone; the storm must push it last.
    planner = TripPlanner(FakeRouter([NORTH, SOUTH]), weather(storm_north))

    result = planner.plan(request())

    assert result.recommendation.recommended_id == "route-2"
    assert result.recommendation.deciding_factor == DecidingFactor.NO_TRAVEL_MILES
    north = next(r for r in result.routes if r.route_id == "route-1")
    assert north.risk.meters_at(RiskLevel.NO_TRAVEL) > 0
    blocked = [c for c in north.checkpoints if c.risk.level == RiskLevel.NO_TRAVEL]
    assert blocked
    assert all(c.risk.drivers[0].factor == Factor.WIND for c in blocked)


@pytest.mark.parametrize(
    ("load_lb", "expected"), [(30_000, RiskLevel.SEVERE), (30_001, RiskLevel.NO_TRAVEL)]
)
def test_load_weight_escalates_wind_risk(load_lb: int, expected: RiskLevel) -> None:
    def windy(location: LatLon, t: int) -> tuple[float, float, float]:
        return (47.0, 0.0, 0.0)

    result = TripPlanner(FakeRouter([DIRECT]), weather(windy)).plan(request(load_lb=load_lb))

    assert {c.risk.level for c in result.routes[0].checkpoints} == {expected}


def test_weather_is_read_at_each_checkpoints_arrival_time() -> None:
    storm_starts = int(DEPART.timestamp()) + 2 * HOUR

    def storm_later(location: LatLon, t: int) -> tuple[float, float, float]:
        return (5.0, 0.6, 0.0) if t > storm_starts else (5.0, 0.0, 0.0)

    result = TripPlanner(FakeRouter([DIRECT]), weather(storm_later)).plan(request())

    for checkpoint in result.routes[0].checkpoints:
        # Rain for an arrival is the total of the hour ending after it.
        expected = RiskLevel.SEVERE if checkpoint.eta.timestamp() > storm_starts else RiskLevel.LOW
        assert checkpoint.risk.level == expected


def test_long_trip_includes_hours_of_service_stops() -> None:
    far = straight_route([ORIGIN, LatLon(40, -80)])  # ~1,700 km, ~19 h of driving
    planner = TripPlanner(FakeRouter([far]), weather())

    with_hos = planner.plan(request(destination=LatLon(40, -80))).routes[0]
    without_hos = planner.plan(request(destination=LatLon(40, -80), enforce_hos=False)).routes[0]

    # 18.9 h of driving: break at 8 h, rest at 11 h; the next break (19 h) is not needed.
    assert [s.kind for s in with_hos.stops] == [StopKind.BREAK, StopKind.REST]
    rest = with_hos.stops[1]
    assert rest.starts_at == DEPART + timedelta(hours=11.5)
    assert rest.ends_at == rest.starts_at + timedelta(hours=10)
    assert meters_to_miles(rest.distance_m) == pytest.approx(11 * HOUR * 25 / 1_609.344)
    assert with_hos.duration_s == pytest.approx(with_hos.driving_s + 10.5 * HOUR)
    assert without_hos.stops == ()
    assert without_hos.duration_s == pytest.approx(without_hos.driving_s)
    # Checkpoints after the rest stop arrive 10.5 h later than without HOS.
    late = with_hos.checkpoints[-1].eta - without_hos.checkpoints[-1].eta
    assert late == timedelta(hours=10.5)


def test_forecasts_fetched_once_with_deduplicated_locations() -> None:
    fake_weather = weather()
    planner = TripPlanner(FakeRouter([NORTH, DIRECT, SOUTH]), fake_weather)

    result = planner.plan(request())

    assert len(fake_weather.calls) == 1
    call = fake_weather.calls[0]
    total_checkpoints = sum(len(r.checkpoints) for r in result.routes)
    # The shared origin and destination are fetched once, not three times.
    assert len(call["locations"]) <= total_checkpoints - 4
    assert call["start"] == DEPART
    assert call["end"] == max(r.arrive_at for r in result.routes)


def test_checkpoints_beyond_the_forecast_are_unknown_and_penalised() -> None:
    planner = TripPlanner(FakeRouter([DIRECT]), weather(hours_available=2))

    route = planner.plan(request()).routes[0]

    unknown = [c for c in route.checkpoints if not c.risk.is_known]
    assert unknown
    assert route.risk.unknown_m > 0
    assert all(c.eta > DEPART + timedelta(hours=1) for c in unknown)


def test_routing_weight_includes_the_truck_itself() -> None:
    router = FakeRouter([DIRECT])

    TripPlanner(router, weather()).plan(request(load_lb=30_000))

    assert router.calls[0].gross_weight_kg == gross_weight_kg(30_000) == 29_484


def test_inconsistent_travel_time_data_is_a_provider_error() -> None:
    broken = ProviderRoute(
        points=DIRECT.points,
        length_m=DIRECT.length_m,
        travel_time_s=100,
        traffic_delay_s=0,
        progress=((0, 0), (1_000, 50), (2_000, 10)),
    )

    with pytest.raises(ProviderError, match="inconsistent travel-time"):
        TripPlanner(FakeRouter([broken]), weather()).plan(request())


def test_polyline_length_is_scaled_to_the_providers_road_length() -> None:
    stretched = straight_route([ORIGIN, DESTINATION], scale=1.02)

    route = TripPlanner(FakeRouter([stretched]), weather()).plan(request()).routes[0]

    assert route.checkpoints[-1].distance_m == pytest.approx(stretched.length_m)
    assert sum(route.risk.meters_by_level.values()) == pytest.approx(stretched.length_m)


def test_long_trips_keep_forecast_locations_within_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    from trips.services import plan_trip

    monkeypatch.setattr(plan_trip, "MAX_WEATHER_LOCATIONS", 20)
    far = straight_route([ORIGIN, LatLon(40, -80)])  # ~1,700 km: ~106 checkpoints at 10 mi
    fake_weather = weather()

    route = (
        TripPlanner(FakeRouter([far]), fake_weather)
        .plan(request(destination=LatLon(40, -80), interval_mi=10))
        .routes[0]
    )

    assert len(route.checkpoints) > 100
    assert len(fake_weather.calls[0]["locations"]) <= 20
    # Every checkpoint still gets weather at its own arrival time.
    assert all(c.risk.is_known for c in route.checkpoints)


def test_weather_grid_stays_fine_for_short_trips() -> None:
    from trips.services.plan_trip import WEATHER_GRID_DEG, weather_grid_deg

    assert weather_grid_deg([ORIGIN, DESTINATION]) == WEATHER_GRID_DEG
