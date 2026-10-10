"""Grid of forecast points covering the corridor around a trip's routes.

Routes are rasterised onto a regular grid (densified so long straight
segments leave no gaps) and the covered cells are dilated by the buffer
radius. Cell size starts fine and grows until the point count fits the
budget, so a short trip gets a detailed heatmap and a cross-country trip
still stays within the weather API's limits.
"""

import math
from collections.abc import Iterator, Sequence
from itertools import pairwise

from trips.domain.geo import LatLon, haversine_m, interpolate

DEFAULT_BUFFER_M = 40_000.0  # ~25 miles either side of the routes
DEFAULT_MAX_POINTS = 150
_METERS_PER_DEGREE = 111_195.0
_GROWTH = 1.1

Cell = tuple[int, int]


def _densify(points: Sequence[LatLon], step_m: float) -> Iterator[LatLon]:
    yield from points[:1]
    for a, b in pairwise(points):
        pieces = max(1, math.ceil(haversine_m(a, b) / step_m))
        for i in range(1, pieces + 1):
            yield interpolate(a, b, i / pieces)


def _grid(
    routes: Sequence[Sequence[LatLon]], cell_m: float, buffer_m: float, lon_scale: float
) -> list[LatLon]:
    cell_lat = cell_m / _METERS_PER_DEGREE
    cell_lon = cell_m / (_METERS_PER_DEGREE * lon_scale)

    covered: set[Cell] = set()
    for route in routes:
        for p in _densify(route, cell_m / 2):
            covered.add((math.floor(p.lat / cell_lat), math.floor(p.lon / cell_lon)))

    radius = math.ceil(buffer_m / cell_m)
    offsets = [
        (dy, dx)
        for dy in range(-radius, radius + 1)
        for dx in range(-radius, radius + 1)
        if dy * dy + dx * dx <= radius * radius
    ]
    cells = {(y + dy, x + dx) for y, x in covered for dy, dx in offsets}
    return [LatLon((y + 0.5) * cell_lat, (x + 0.5) * cell_lon) for y, x in sorted(cells)]


def corridor_points(
    routes: Sequence[Sequence[LatLon]],
    buffer_m: float = DEFAULT_BUFFER_M,
    max_points: int = DEFAULT_MAX_POINTS,
) -> list[LatLon]:
    """Cell centres within ~`buffer_m` of any route, at most `max_points` of them."""
    if buffer_m <= 0 or max_points <= 0:
        raise ValueError("buffer_m and max_points must be positive.")
    all_points = [p for route in routes for p in route]
    if not all_points:
        return []

    # One longitude scale for the whole grid keeps it regular; across a trip's
    # latitude span the distortion is a few percent.
    mean_lat = sum(p.lat for p in all_points) / len(all_points)
    lon_scale = max(math.cos(math.radians(mean_lat)), 0.1)

    cell_m = buffer_m / 4
    while True:
        points = _grid(routes, cell_m, buffer_m, lon_scale)
        if len(points) <= max_points:
            return points
        cell_m *= _GROWTH
