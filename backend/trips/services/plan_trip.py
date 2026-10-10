"""Plan a trip: routes, checkpoint weather at arrival time, risk and a recommendation.

Pipeline: collect route options -> sample checkpoints every N miles -> work out
when the truck reaches each one (traffic-aware driving time plus hours-of-
service stops) -> fetch forecasts for every checkpoint in one batched request
-> classify risk with the load rules -> score each route -> rank.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from trips.domain.eta import TimeProfile
from trips.domain.forecast import HourlySeries
from trips.domain.geo import (
    LatLon,
    cumulative_distances_m,
    miles_to_meters,
    point_at_distance,
)
from trips.domain.hos import DrivingSchedule, StopKind
from trips.domain.recommend import Recommendation, RouteCandidate, recommend
from trips.domain.risk import RiskAssessment, WeatherSample, classify
from trips.domain.sampling import sample_checkpoints
from trips.domain.scoring import CheckpointLevel, RouteRisk, score_route
from trips.providers.base import ProviderRoute, RoutingProvider, WeatherProvider
from trips.providers.http import ProviderError
from trips.services.route_options import RouteQuery, collect_route_options

KG_PER_LB = 0.45359237
# The brief's load weight is cargo; routing needs the whole vehicle's weight
# to respect weight-restricted roads. A typical empty tractor-trailer is ~35,000 lb.
TYPICAL_TARE_LB = 35_000
# Checkpoints in the same grid cell share one forecast location. The cell starts
# at ~2 km (finer than the weather models' grid, so no detail is lost) and grows
# only when a trip would need more than MAX_WEATHER_LOCATIONS, which keeps very
# long trips within the weather API's per-minute limit. Even fully coarsened,
# cells stay near the ~13-25 km grid of the models forecasting beyond 2 days.
WEATHER_GRID_DEG = 0.02
WEATHER_GRID_GROWTH = 1.5
MAX_WEATHER_LOCATIONS = 200


@dataclass(frozen=True, slots=True)
class TripRequest:
    origin: LatLon
    destination: LatLon
    depart_at: datetime
    load_lb: float
    interval_mi: int
    enforce_hos: bool = True


@dataclass(frozen=True, slots=True)
class PlannedCheckpoint:
    distance_m: float
    position: LatLon
    eta: datetime
    weather: WeatherSample
    risk: RiskAssessment


@dataclass(frozen=True, slots=True)
class PlannedStop:
    kind: StopKind
    distance_m: float
    position: LatLon
    starts_at: datetime
    ends_at: datetime


@dataclass(frozen=True, slots=True)
class PlannedRoute:
    route_id: str
    points: tuple[LatLon, ...]
    distance_m: float
    driving_s: float
    duration_s: float
    """Door to door, including hours-of-service stops."""
    traffic_delay_s: float
    arrive_at: datetime
    checkpoints: tuple[PlannedCheckpoint, ...]
    stops: tuple[PlannedStop, ...]
    risk: RouteRisk


@dataclass(frozen=True, slots=True)
class TripPlan:
    request: TripRequest
    routes: tuple[PlannedRoute, ...]
    """In ranked order, best first."""
    recommendation: Recommendation


@dataclass(frozen=True, slots=True)
class _RouteTiming:
    route_id: str
    provider_route: ProviderRoute
    cumulative_m: list[float]
    profile: TimeProfile
    schedule: DrivingSchedule
    checkpoint_offsets: list[tuple[float, LatLon, datetime]]


class TripPlanner:
    def __init__(self, router: RoutingProvider, weather: WeatherProvider) -> None:
        self._router = router
        self._weather = weather

    def plan(self, request: TripRequest) -> TripPlan:
        provider_routes = collect_route_options(
            self._router,
            RouteQuery(
                origin=request.origin,
                destination=request.destination,
                depart_at=request.depart_at,
                gross_weight_kg=gross_weight_kg(request.load_lb),
            ),
        )
        timings = [
            _time_route(f"route-{i}", route, request)
            for i, route in enumerate(provider_routes, start=1)
        ]
        forecasts = self._forecasts(timings, request.depart_at)

        routes = [_assess_route(t, request, forecasts) for t in timings]
        recommendation = recommend(
            [
                RouteCandidate(r.route_id, r.risk, duration_s=r.duration_s, distance_m=r.distance_m)
                for r in routes
            ]
        )
        by_id = {r.route_id: r for r in routes}
        return TripPlan(
            request=request,
            routes=tuple(by_id[route_id] for route_id in recommendation.ranked_ids),
            recommendation=recommendation,
        )

    def _forecasts(self, timings: Sequence[_RouteTiming], depart_at: datetime) -> "_Forecasts":
        positions = [position for t in timings for _, position, _ in t.checkpoint_offsets]
        grid_deg = weather_grid_deg(positions)
        cells = sorted({_grid_cell(p, grid_deg) for p in positions})
        latest = max(eta for t in timings for _, _, eta in t.checkpoint_offsets)
        series = self._weather.hourly(
            [LatLon(lat * grid_deg, lon * grid_deg) for lat, lon in cells],
            depart_at,
            latest,
        )
        return _Forecasts(grid_deg, dict(zip(cells, series, strict=True)))


@dataclass(frozen=True, slots=True)
class _Forecasts:
    grid_deg: float
    by_cell: dict[tuple[int, int], HourlySeries]

    def at(self, position: LatLon, when: datetime) -> WeatherSample:
        return self.by_cell[_grid_cell(position, self.grid_deg)].sample_at(when.timestamp())


def weather_grid_deg(positions: Sequence[LatLon]) -> float:
    """Finest grid (from ~2 km) that keeps distinct forecast locations within budget."""
    grid_deg = WEATHER_GRID_DEG
    while len({_grid_cell(p, grid_deg) for p in positions}) > MAX_WEATHER_LOCATIONS:
        grid_deg *= WEATHER_GRID_GROWTH
    return grid_deg


def gross_weight_kg(load_lb: float) -> int:
    return round((load_lb + TYPICAL_TARE_LB) * KG_PER_LB)


def _grid_cell(position: LatLon, grid_deg: float) -> tuple[int, int]:
    return round(position.lat / grid_deg), round(position.lon / grid_deg)


def _time_route(route_id: str, route: ProviderRoute, request: TripRequest) -> _RouteTiming:
    """Checkpoint positions and arrival times for one route."""
    try:
        profile = TimeProfile.from_anchors(route.progress)
    except ValueError:
        raise ProviderError("Routing", "returned inconsistent travel-time data") from None

    # Our polyline length differs slightly from the provider's road length;
    # scale it so checkpoint distances and progress anchors share one measure.
    measured = cumulative_distances_m(route.points)
    scale = route.length_m / measured[-1] if measured[-1] > 0 else 1.0
    cumulative = [d * scale for d in measured]

    schedule = DrivingSchedule.plan(profile.total_seconds, enforce_hos=request.enforce_hos)
    offsets = [
        (
            c.distance_m,
            c.position,
            request.depart_at
            + timedelta(seconds=schedule.elapsed_at(profile.seconds_at(c.distance_m))),
        )
        for c in sample_checkpoints(route.points, cumulative, miles_to_meters(request.interval_mi))
    ]
    return _RouteTiming(route_id, route, cumulative, profile, schedule, offsets)


def _assess_route(
    timing: _RouteTiming,
    request: TripRequest,
    forecasts: _Forecasts,
) -> PlannedRoute:
    checkpoints = []
    for distance, position, eta in timing.checkpoint_offsets:
        weather = forecasts.at(position, eta)
        assessment = classify(weather, request.load_lb)
        checkpoints.append(PlannedCheckpoint(distance, position, eta, weather, assessment))

    route = timing.provider_route
    route_risk = score_route(
        [CheckpointLevel(c.distance_m, c.risk.level) for c in checkpoints],
        total_m=timing.cumulative_m[-1],
    )
    duration = timing.schedule.total_elapsed_s
    return PlannedRoute(
        route_id=timing.route_id,
        points=route.points,
        distance_m=route.length_m,
        driving_s=timing.profile.total_seconds,
        duration_s=duration,
        traffic_delay_s=route.traffic_delay_s,
        arrive_at=request.depart_at + timedelta(seconds=duration),
        checkpoints=tuple(checkpoints),
        stops=tuple(_stops(timing, request.depart_at)),
        risk=route_risk,
    )


def _stops(timing: _RouteTiming, depart_at: datetime) -> list[PlannedStop]:
    stops = []
    for stop in timing.schedule.stops:
        distance = timing.profile.distance_at(stop.driving_offset_s)
        starts_at = depart_at + timedelta(seconds=timing.schedule.elapsed_at(stop.driving_offset_s))
        stops.append(
            PlannedStop(
                kind=stop.kind,
                distance_m=distance,
                position=point_at_distance(
                    timing.provider_route.points, timing.cumulative_m, distance
                ),
                starts_at=starts_at,
                ends_at=starts_at + timedelta(seconds=stop.duration_s),
            )
        )
    return stops
