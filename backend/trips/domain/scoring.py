"""Route-level risk metrics from checkpoint risk levels.

Checkpoints are points, but the recommendation rules count *miles*. Each
checkpoint therefore represents the stretch of road nearest to it: from the
midpoint with the previous checkpoint to the midpoint with the next one (the
first starts at the origin, the last ends at the destination). The stretches
tile the route exactly, so per-level distances always sum to its length, and a
shorter final interval correctly carries less weight.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from itertools import pairwise

from trips.domain.risk import RiskLevel


@dataclass(frozen=True, slots=True)
class CheckpointLevel:
    distance_m: float
    level: RiskLevel | None
    """`None` when weather data for the checkpoint is unavailable."""


@dataclass(frozen=True, slots=True)
class RouteRisk:
    total_m: float
    meters_by_level: dict[RiskLevel, float] = field(default_factory=dict)
    unknown_m: float = 0.0
    average_score: float | None = None
    """Distance-weighted mean of risk scores (Low=0 ... No Travel=4) over known stretches."""
    worst_level: RiskLevel | None = None

    def meters_at(self, level: RiskLevel) -> float:
        return self.meters_by_level.get(level, 0.0)


def stretch_lengths_m(distances_m: Sequence[float], total_m: float) -> list[float]:
    """Length of road each checkpoint represents (midpoint ownership)."""
    if not distances_m:
        raise ValueError("At least one checkpoint is required.")
    if any(b < a for a, b in pairwise(distances_m)):
        raise ValueError("Checkpoints must be ordered by distance.")
    if distances_m[0] < 0 or distances_m[-1] > total_m:
        raise ValueError("Checkpoints must lie within the route.")

    boundaries = [0.0]
    boundaries += [(a + b) / 2 for a, b in pairwise(distances_m)]
    boundaries.append(total_m)
    return [end - start for start, end in pairwise(boundaries)]


def score_route(checkpoints: Sequence[CheckpointLevel], total_m: float) -> RouteRisk:
    lengths = stretch_lengths_m([c.distance_m for c in checkpoints], total_m)

    meters_by_level = dict.fromkeys(RiskLevel, 0.0)
    unknown_m = 0.0
    for checkpoint, length in zip(checkpoints, lengths, strict=True):
        if checkpoint.level is None:
            unknown_m += length
        else:
            meters_by_level[checkpoint.level] += length

    known = [c.level for c in checkpoints if c.level is not None]
    known_m = sum(meters_by_level.values())
    if known_m > 0:
        average: float | None = sum(int(lvl) * m for lvl, m in meters_by_level.items()) / known_m
    elif known:
        # Zero-length route: fall back to an unweighted mean.
        average = sum(int(lvl) for lvl in known) / len(known)
    else:
        average = None

    return RouteRisk(
        total_m=total_m,
        meters_by_level=meters_by_level,
        unknown_m=unknown_m,
        average_score=average,
        worst_level=max(known) if known else None,
    )
