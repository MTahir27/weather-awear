"""Geometry helpers for route polylines.

Distances are in meters. Interpolation between consecutive polyline points is
linear in latitude/longitude, which is accurate for the short segments of a
routing polyline (typically tens of meters apart).
"""

import math
from bisect import bisect_right
from collections.abc import Sequence
from itertools import pairwise
from typing import NamedTuple

EARTH_RADIUS_M = 6_371_008.8
METERS_PER_MILE = 1_609.344


class LatLon(NamedTuple):
    lat: float
    lon: float


def miles_to_meters(miles: float) -> float:
    return miles * METERS_PER_MILE


def meters_to_miles(meters: float) -> float:
    return meters / METERS_PER_MILE


def haversine_m(a: LatLon, b: LatLon) -> float:
    """Great-circle distance between two points."""
    lat1, lon1, lat2, lon2 = map(math.radians, (a.lat, a.lon, b.lat, b.lon))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(min(1.0, h)))


def cumulative_distances_m(points: Sequence[LatLon]) -> list[float]:
    """Distance from the first point to every point along the polyline."""
    if not points:
        raise ValueError("A polyline needs at least one point.")
    distances = [0.0]
    for previous, current in pairwise(points):
        distances.append(distances[-1] + haversine_m(previous, current))
    return distances


def interpolate(a: LatLon, b: LatLon, fraction: float) -> LatLon:
    return LatLon(a.lat + (b.lat - a.lat) * fraction, a.lon + (b.lon - a.lon) * fraction)


def point_at_distance(
    points: Sequence[LatLon], cumulative_m: Sequence[float], distance_m: float
) -> LatLon:
    """Position along the polyline at `distance_m` from its start.

    Distances outside the polyline are clamped to its ends.
    """
    if len(points) != len(cumulative_m) or not points:
        raise ValueError("points and cumulative_m must be non-empty and the same length.")
    if distance_m <= 0:
        return points[0]
    if distance_m >= cumulative_m[-1]:
        return points[-1]

    upper = bisect_right(cumulative_m, distance_m)
    lower = upper - 1
    span = cumulative_m[upper] - cumulative_m[lower]
    fraction = (distance_m - cumulative_m[lower]) / span if span > 0 else 0.0
    return interpolate(points[lower], points[upper], fraction)
