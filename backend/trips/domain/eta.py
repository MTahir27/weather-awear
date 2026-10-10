"""Driving time along a route as a function of distance.

The routing provider reports progress anchors (distance, driving time) along
the route. These reflect the real speed profile, including slower city
stretches and expected traffic at departure time, so ETAs at checkpoints are
interpolated between anchors rather than derived from an average speed.
"""

from bisect import bisect_left, bisect_right
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TimeProfile:
    """Piecewise-linear mapping from distance (m) to driving time (s)."""

    distances_m: tuple[float, ...]
    seconds: tuple[float, ...]

    def __post_init__(self) -> None:
        if not self.distances_m or len(self.distances_m) != len(self.seconds):
            raise ValueError("A time profile needs matching, non-empty distance and time series.")
        if self.distances_m[0] != 0 or self.seconds[0] != 0:
            raise ValueError("A time profile must start at distance 0 and time 0.")
        for i in range(1, len(self.distances_m)):
            if self.distances_m[i] <= self.distances_m[i - 1]:
                raise ValueError("Profile distances must be strictly increasing.")
            if self.seconds[i] < self.seconds[i - 1]:
                raise ValueError("Driving time cannot decrease along the route.")

    @classmethod
    def from_anchors(cls, anchors: Iterable[tuple[float, float]]) -> "TimeProfile":
        """Build from (distance_m, seconds) anchors in route order.

        Repeated distances (e.g. a stop with no movement) keep the latest time.
        """
        distances: list[float] = []
        seconds: list[float] = []
        for distance, time in anchors:
            if distances and distance == distances[-1]:
                seconds[-1] = time
            else:
                distances.append(distance)
                seconds.append(time)
        return cls(tuple(distances), tuple(seconds))

    @property
    def total_distance_m(self) -> float:
        return self.distances_m[-1]

    @property
    def total_seconds(self) -> float:
        return self.seconds[-1]

    def seconds_at(self, distance_m: float) -> float:
        """Driving time to reach `distance_m`, clamped to the route's extent."""
        if distance_m <= 0:
            return 0.0
        if distance_m >= self.total_distance_m:
            return self.total_seconds

        upper = bisect_right(self.distances_m, distance_m)
        lower = upper - 1
        fraction = (distance_m - self.distances_m[lower]) / (
            self.distances_m[upper] - self.distances_m[lower]
        )
        return self.seconds[lower] + fraction * (self.seconds[upper] - self.seconds[lower])

    def distance_at(self, seconds: float) -> float:
        """Distance reached after `seconds` of driving, clamped to the route's extent.

        Where several anchors share the same time, the first distance at which
        that time is reached is returned.
        """
        if seconds <= 0:
            return 0.0
        if seconds >= self.total_seconds:
            return self.total_distance_m

        upper = bisect_left(self.seconds, seconds)
        lower = upper - 1
        fraction = (seconds - self.seconds[lower]) / (self.seconds[upper] - self.seconds[lower])
        return self.distances_m[lower] + fraction * (
            self.distances_m[upper] - self.distances_m[lower]
        )
