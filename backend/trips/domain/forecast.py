"""Reading an hourly forecast at the moment the truck reaches a point.

Hourly precipitation values are totals for the hour *ending* at their
timestamp, so an arrival at 14:20 uses the value stamped 15:00. Wind is an
instantaneous value at each timestamp, so it is interpolated linearly between
the surrounding hours. Times outside the forecast give an unknown sample
instead of guessing.
"""

from bisect import bisect_left
from collections.abc import Sequence
from dataclasses import dataclass

from trips.domain.risk import WeatherSample

UNKNOWN = WeatherSample(wind_mph=None, rain_in_per_hr=None, snow_in_per_hr=None)


@dataclass(frozen=True, slots=True)
class HourlySeries:
    """Hourly forecast for one location. Times are Unix seconds, ascending."""

    times: tuple[int, ...]
    wind_mph: tuple[float | None, ...]
    gust_mph: tuple[float | None, ...]
    rain_in: tuple[float | None, ...]
    """Liquid precipitation (rain + showers) in the preceding hour."""
    snow_in: tuple[float | None, ...]
    """Snowfall in the preceding hour."""

    def __post_init__(self) -> None:
        n = len(self.times)
        if n == 0:
            raise ValueError("A forecast needs at least one hour.")
        if any(len(s) != n for s in (self.wind_mph, self.gust_mph, self.rain_in, self.snow_in)):
            raise ValueError("Every forecast variable needs one value per hour.")
        if any(b <= a for a, b in zip(self.times, self.times[1:], strict=False)):
            raise ValueError("Forecast times must be strictly increasing.")

    @property
    def start(self) -> int:
        return self.times[0]

    @property
    def end(self) -> int:
        return self.times[-1]

    def sample_at(self, unix_s: float) -> WeatherSample:
        if not self.start <= unix_s <= self.end:
            return UNKNOWN

        # First hour stamped at or after the arrival: its precipitation covers it.
        bucket = bisect_left(self.times, unix_s)
        return WeatherSample(
            wind_mph=_interpolate(self.times, self.wind_mph, unix_s, bucket),
            gust_mph=_interpolate(self.times, self.gust_mph, unix_s, bucket),
            rain_in_per_hr=self.rain_in[bucket],
            snow_in_per_hr=self.snow_in[bucket],
        )


def _interpolate(
    times: Sequence[int], values: Sequence[float | None], t: float, upper: int
) -> float | None:
    if times[upper] == t or upper == 0:
        return values[upper]
    lower = upper - 1
    a, b = values[lower], values[upper]
    if a is None or b is None:
        return None
    fraction = (t - times[lower]) / (times[upper] - times[lower])
    return a + (b - a) * fraction
