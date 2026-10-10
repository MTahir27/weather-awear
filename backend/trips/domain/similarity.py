"""How much two routes overlap, to discard near-duplicate alternatives.

Route B is rasterised onto a grid of cells about `tolerance_m` wide. Route A
is then walked in steps of half that size, and each step counts as shared if
its cell or a neighbouring cell is covered by B. Long straight segments are
densified first so sparse polylines are handled correctly.
"""

import math
from collections.abc import Iterator, Sequence
from itertools import pairwise

from trips.domain.geo import LatLon, haversine_m, interpolate

DEFAULT_TOLERANCE_M = 300.0
_METERS_PER_DEGREE = 111_195.0

Cell = tuple[int, int]


def _cell(point: LatLon, size_deg: float) -> Cell:
    # Scale longitude so cells are roughly square away from the equator.
    lon_scale = math.cos(math.radians(point.lat))
    return math.floor(point.lat / size_deg), math.floor(point.lon * lon_scale / size_deg)


def _samples(points: Sequence[LatLon], step_m: float) -> Iterator[tuple[LatLon, float]]:
    """Points along the polyline at most `step_m` apart, with the length each represents."""
    for a, b in pairwise(points):
        length = haversine_m(a, b)
        if length == 0:
            continue
        pieces = max(1, math.ceil(length / step_m))
        for i in range(pieces):
            yield interpolate(a, b, (i + 0.5) / pieces), length / pieces


def overlap_fraction(
    a: Sequence[LatLon], b: Sequence[LatLon], tolerance_m: float = DEFAULT_TOLERANCE_M
) -> float:
    """Share of route `a`'s length that runs within ~`tolerance_m` of route `b`."""
    size_deg = tolerance_m / _METERS_PER_DEGREE
    step_m = tolerance_m / 2

    covered: set[Cell] = {_cell(p, size_deg) for p in b}
    covered.update(_cell(p, size_deg) for p, _ in _samples(b, step_m))

    shared = total = 0.0
    for point, length in _samples(a, step_m):
        total += length
        lat_cell, lon_cell = _cell(point, size_deg)
        if any((lat_cell + dy, lon_cell + dx) in covered for dy in (-1, 0, 1) for dx in (-1, 0, 1)):
            shared += length
    return shared / total if total else 1.0


def is_distinct(
    candidate: Sequence[LatLon],
    existing: Sequence[Sequence[LatLon]],
    max_overlap: float = 0.9,
) -> bool:
    """True if `candidate` overlaps each existing route by less than `max_overlap`.

    Overlap is checked both ways, so a route that is a near-subset of another
    (or the other way round) also counts as a duplicate.
    """
    return all(
        max(overlap_fraction(candidate, route), overlap_fraction(route, candidate)) < max_overlap
        for route in existing
    )
