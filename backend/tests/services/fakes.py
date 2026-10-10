"""In-memory provider fakes for service and API tests."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from trips.domain.forecast import HourlySeries
from trips.domain.geo import LatLon, cumulative_distances_m
from trips.providers.base import Avoid, ProviderRoute


def straight_route(
    points: Sequence[LatLon], *, speed_mps: float = 25.0, scale: float = 1.0
) -> ProviderRoute:
    """A route along `points` at constant speed. `scale` stretches the reported length."""
    cumulative = cumulative_distances_m(points)
    length = cumulative[-1] * scale
    time = length / speed_mps
    return ProviderRoute(
        points=tuple(points),
        length_m=length,
        travel_time_s=time,
        traffic_delay_s=0,
        progress=((0.0, 0.0), (length, time)),
    )


@dataclass
class RouterCall:
    via: tuple[LatLon, ...]
    avoid: tuple[Avoid, ...]
    max_alternatives: int
    gross_weight_kg: int
    depart_at: datetime


def _no_fallbacks(call: RouterCall) -> list[ProviderRoute]:
    return []


@dataclass
class FakeRouter:
    """Returns `main` for plain requests; `respond` answers via/avoid requests."""

    main: list[ProviderRoute]
    respond: Callable[[RouterCall], list[ProviderRoute]] = _no_fallbacks
    calls: list[RouterCall] = field(default_factory=list)

    def truck_routes(
        self,
        origin: LatLon,
        destination: LatLon,
        *,
        depart_at: datetime,
        gross_weight_kg: int,
        max_alternatives: int = 0,
        via: Sequence[LatLon] = (),
        avoid: Sequence[Avoid] = (),
    ) -> list[ProviderRoute]:
        call = RouterCall(tuple(via), tuple(avoid), max_alternatives, gross_weight_kg, depart_at)
        self.calls.append(call)
        if not via and not avoid:
            return list(self.main)
        return self.respond(call)


@dataclass
class FakeWeather:
    """Builds each location's forecast with `series_for`."""

    series_for: Callable[[LatLon, datetime, datetime], HourlySeries]
    calls: list[dict[str, Any]] = field(default_factory=list)

    def hourly(
        self, locations: Sequence[LatLon], start: datetime, end: datetime
    ) -> list[HourlySeries]:
        self.calls.append({"locations": list(locations), "start": start, "end": end})
        return [self.series_for(loc, start, end) for loc in locations]
