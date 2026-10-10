"""Hourly weather and risk frames across the trip corridor.

Frame k describes conditions at departure + k hours, sampled and classified
exactly like route checkpoints (precipitation for the hour ending after that
time, interpolated wind, load rules applied), so the heatmap and the route
colours always agree.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from trips.domain.corridor import corridor_points
from trips.domain.geo import LatLon
from trips.domain.risk import classify
from trips.providers.base import WeatherProvider

HEATMAP_HOURS = 48
UNKNOWN_LEVEL = -1


@dataclass(frozen=True, slots=True)
class HeatmapRequest:
    routes: Sequence[Sequence[LatLon]]
    depart_at: datetime
    load_lb: float
    hours: int = HEATMAP_HOURS


@dataclass(frozen=True, slots=True)
class Heatmap:
    depart_at: datetime
    points: tuple[LatLon, ...]
    risk: list[list[int]]
    """[frame][point] risk level 0-4, or -1 where the forecast is unavailable."""
    wind_mph: list[list[float | None]]
    rain_in_per_hr: list[list[float | None]]
    snow_in_per_hr: list[list[float | None]]

    @property
    def frame_count(self) -> int:
        return len(self.risk)


class HeatmapBuilder:
    def __init__(self, weather: WeatherProvider) -> None:
        self._weather = weather

    def build(self, request: HeatmapRequest) -> Heatmap:
        points = corridor_points(request.routes)
        frame_times = [request.depart_at + timedelta(hours=k) for k in range(request.hours + 1)]
        forecasts = self._weather.hourly(points, frame_times[0], frame_times[-1]) if points else []

        risk: list[list[int]] = []
        wind: list[list[float | None]] = []
        rain: list[list[float | None]] = []
        snow: list[list[float | None]] = []
        for t in frame_times:
            samples = [series.sample_at(t.timestamp()) for series in forecasts]
            levels = [classify(s, request.load_lb).level for s in samples]
            risk.append([UNKNOWN_LEVEL if lvl is None else int(lvl) for lvl in levels])
            wind.append([s.wind_mph for s in samples])
            rain.append([s.rain_in_per_hr for s in samples])
            snow.append([s.snow_in_per_hr for s in samples])

        return Heatmap(
            depart_at=request.depart_at,
            points=tuple(points),
            risk=risk,
            wind_mph=wind,
            rain_in_per_hr=rain,
            snow_in_per_hr=snow,
        )
