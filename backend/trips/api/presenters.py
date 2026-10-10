"""JSON representation of a trip plan.

Field names carry their units (`_mi`, `_s`, `_mph`, `_in_per_hr`). Times are
ISO 8601 in UTC; the client converts them for display.
"""

from datetime import UTC, datetime
from typing import Any

from trips.domain.geo import meters_to_miles
from trips.domain.polyline import encode, simplify
from trips.domain.risk import RiskLevel
from trips.services.heatmap import Heatmap
from trips.services.plan_trip import PlannedCheckpoint, PlannedRoute, PlannedStop, TripPlan

GEOMETRY_TOLERANCE_M = 15.0


def _iso(t: datetime) -> str:
    return t.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _level(level: RiskLevel | None) -> str | None:
    return None if level is None else level.name.lower()


def _miles(meters: float) -> float:
    return round(meters_to_miles(meters), 2)


def _round(value: float | None, digits: int) -> float | None:
    return None if value is None else round(value, digits)


def present_plan(plan: TripPlan) -> dict[str, Any]:
    recommendation = plan.recommendation
    request = plan.request
    return {
        "departure_time": _iso(request.depart_at),
        "load_weight_lb": request.load_lb,
        "sample_interval_mi": request.interval_mi,
        "hours_of_service": request.enforce_hos,
        "recommendation": {
            "route_id": recommendation.recommended_id,
            "travel_advised": recommendation.travel_advised,
            "deciding_factor": recommendation.deciding_factor.value,
            "explanation": recommendation.explanation,
        },
        "routes": [
            _route(route, rank, route.route_id == recommendation.recommended_id)
            for rank, route in enumerate(plan.routes, start=1)
        ],
    }


def _route(route: PlannedRoute, rank: int, recommended: bool) -> dict[str, Any]:
    risk = route.risk
    return {
        "id": route.route_id,
        "rank": rank,
        "recommended": recommended,
        "geometry": encode(simplify(route.points, GEOMETRY_TOLERANCE_M)),
        "distance_mi": _miles(route.distance_m),
        "driving_s": round(route.driving_s),
        "duration_s": round(route.duration_s),
        "traffic_delay_s": round(route.traffic_delay_s),
        "arrival_time": _iso(route.arrive_at),
        "risk": {
            "miles_by_level": {_level(lvl): _miles(m) for lvl, m in risk.meters_by_level.items()},
            "unknown_mi": _miles(risk.unknown_m),
            "average": _round(risk.average_score, 3),
            "worst_level": _level(risk.worst_level),
        },
        "checkpoints": [_checkpoint(c) for c in route.checkpoints],
        "stops": [_stop(s) for s in route.stops],
    }


def _checkpoint(checkpoint: PlannedCheckpoint) -> dict[str, Any]:
    weather = checkpoint.weather
    risk = checkpoint.risk
    return {
        "mile": _miles(checkpoint.distance_m),
        "lat": round(checkpoint.position.lat, 5),
        "lon": round(checkpoint.position.lon, 5),
        "eta": _iso(checkpoint.eta),
        "level": _level(risk.level),
        "wind_mph": _round(weather.wind_mph, 1),
        "gust_mph": _round(weather.gust_mph, 1),
        "rain_in_per_hr": _round(weather.rain_in_per_hr, 3),
        "snow_in_per_hr": _round(weather.snow_in_per_hr, 3),
        "drivers": [d.factor.value for d in risk.drivers],
        "load_escalated": risk.load_escalated,
    }


def _stop(stop: PlannedStop) -> dict[str, Any]:
    return {
        "kind": stop.kind.value,
        "mile": _miles(stop.distance_m),
        "lat": round(stop.position.lat, 5),
        "lon": round(stop.position.lon, 5),
        "starts_at": _iso(stop.starts_at),
        "ends_at": _iso(stop.ends_at),
    }


def present_heatmap(heatmap: Heatmap) -> dict[str, Any]:
    """Column-oriented arrays: frame k, point i is `risk[k][i]`, at (lat[i], lon[i])."""

    def frames(values: list[list[float | None]], digits: int) -> list[list[float | None]]:
        return [[_round(v, digits) for v in frame] for frame in values]

    return {
        "departure_time": _iso(heatmap.depart_at),
        "frame_hours": 1,
        "lat": [round(p.lat, 4) for p in heatmap.points],
        "lon": [round(p.lon, 4) for p in heatmap.points],
        "risk": heatmap.risk,
        "wind_score": frames(heatmap.wind_score, 2),
        "rain_score": frames(heatmap.rain_score, 2),
        "snow_score": frames(heatmap.snow_score, 2),
    }
