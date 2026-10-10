"""Checkpoint placement along a route.

Checkpoints sit every `interval` meters from the origin, plus one at the
destination, so both trip ends are always assessed. Offsets are computed as
integer multiples of the interval to avoid accumulating floating-point drift.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from trips.domain.geo import LatLon, point_at_distance

# A final interval shorter than this is treated as already reaching the destination.
_END_TOLERANCE_M = 1.0


@dataclass(frozen=True, slots=True)
class Checkpoint:
    index: int
    distance_m: float
    position: LatLon


def checkpoint_offsets_m(total_m: float, interval_m: float) -> list[float]:
    """Distances from the origin at which to place checkpoints."""
    if total_m < 0:
        raise ValueError(f"Route length cannot be negative, got {total_m}.")
    if interval_m <= 0:
        raise ValueError(f"Sampling interval must be positive, got {interval_m}.")

    offsets = []
    step = 0
    while step * interval_m < total_m - _END_TOLERANCE_M:
        offsets.append(step * interval_m)
        step += 1
    offsets.append(total_m)
    return offsets


def sample_checkpoints(
    points: Sequence[LatLon], cumulative_m: Sequence[float], interval_m: float
) -> list[Checkpoint]:
    """Checkpoints every `interval_m` along the polyline, including both ends."""
    return [
        Checkpoint(
            index=i, distance_m=offset, position=point_at_distance(points, cumulative_m, offset)
        )
        for i, offset in enumerate(checkpoint_offsets_m(cumulative_m[-1], interval_m))
    ]
