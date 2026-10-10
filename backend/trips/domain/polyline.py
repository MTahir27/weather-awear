"""Compact route geometry for the API.

Routing polylines carry ~10 points per kilometre. They are simplified with
Ramer-Douglas-Peucker (dropping points that deviate less than a tolerance from
the simplified line) and encoded with Google's polyline algorithm, cutting
payloads by well over 90% with no visible change at map zoom levels.
"""

import math
from collections.abc import Sequence

from trips.domain.geo import LatLon

_METERS_PER_DEGREE = 111_195.0


def _offset_m(point: LatLon, start: LatLon, end: LatLon) -> float:
    """Distance from `point` to the segment start-end, on a local flat projection."""
    scale = math.cos(math.radians(start.lat))
    px, py = (point.lon - start.lon) * scale, point.lat - start.lat
    ex, ey = (end.lon - start.lon) * scale, end.lat - start.lat
    length_sq = ex * ex + ey * ey
    if length_sq == 0:
        return math.hypot(px, py) * _METERS_PER_DEGREE
    t = max(0.0, min(1.0, (px * ex + py * ey) / length_sq))
    return math.hypot(px - t * ex, py - t * ey) * _METERS_PER_DEGREE


def simplify(points: Sequence[LatLon], tolerance_m: float) -> list[LatLon]:
    """Ramer-Douglas-Peucker simplification (iterative, so long routes are safe)."""
    if len(points) < 3:
        return list(points)
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        first, last = stack.pop()
        furthest, max_offset = -1, tolerance_m
        for i in range(first + 1, last):
            offset = _offset_m(points[i], points[first], points[last])
            if offset > max_offset:
                furthest, max_offset = i, offset
        if furthest != -1:
            keep[furthest] = True
            stack += [(first, furthest), (furthest, last)]
    return [p for p, kept in zip(points, keep, strict=True) if kept]


def encode(points: Sequence[LatLon], precision: int = 5) -> str:
    """Google encoded polyline (https://developers.google.com/maps/documentation/utilities/polylinealgorithm)."""
    factor = 10**precision
    chunks: list[str] = []
    previous_lat = previous_lon = 0
    for point in points:
        lat, lon = round(point.lat * factor), round(point.lon * factor)
        for delta in (lat - previous_lat, lon - previous_lon):
            value = ~(delta << 1) if delta < 0 else delta << 1
            while value >= 0x20:
                chunks.append(chr((0x20 | (value & 0x1F)) + 63))
                value >>= 5
            chunks.append(chr(value + 63))
        previous_lat, previous_lon = lat, lon
    return "".join(chunks)


def decode(encoded: str, precision: int = 5) -> list[LatLon]:
    """Inverse of `encode`. Raises ValueError on malformed input."""
    factor = 10**precision
    points: list[LatLon] = []
    index = lat = lon = 0

    def next_delta() -> int:
        nonlocal index
        result = shift = 0
        while True:
            if index >= len(encoded):
                raise ValueError("Malformed polyline.")
            byte = ord(encoded[index]) - 63
            index += 1
            if not 0 <= byte < 64:
                raise ValueError("Malformed polyline.")
            result |= (byte & 0x1F) << shift
            shift += 5
            if byte < 0x20:
                return ~(result >> 1) if result & 1 else result >> 1

    while index < len(encoded):
        lat += next_delta()
        lon += next_delta()
        points.append(LatLon(lat / factor, lon / factor))
    return points
