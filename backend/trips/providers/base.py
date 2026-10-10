"""Provider-neutral interfaces and data types.

The trip planning service depends only on these protocols, so providers can
be swapped (or faked in tests) without touching business logic.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from trips.domain.forecast import HourlySeries
from trips.domain.geo import LatLon


@dataclass(frozen=True, slots=True)
class Place:
    label: str
    position: LatLon


class Geocoder(Protocol):
    def search(self, query: str, *, limit: int = 5) -> list[Place]: ...


class NoRouteFound(Exception):
    """No drivable route exists between the requested points."""


class Avoid(StrEnum):
    MOTORWAYS = "motorways"
    TOLL_ROADS = "tollRoads"


@dataclass(frozen=True, slots=True)
class ProviderRoute:
    points: tuple[LatLon, ...]
    length_m: float
    travel_time_s: float
    """Driving time, including expected traffic at the departure time."""
    traffic_delay_s: float
    progress: tuple[tuple[float, float], ...]
    """(distance_m, driving_s) anchors along the route, starting at (0, 0)."""


class RoutingProvider(Protocol):
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
    ) -> list[ProviderRoute]: ...


class WeatherProvider(Protocol):
    def hourly(
        self, locations: Sequence[LatLon], start: datetime, end: datetime
    ) -> list[HourlySeries]:
        """Hourly forecasts covering [start, end], one per location, in input order."""
        ...
