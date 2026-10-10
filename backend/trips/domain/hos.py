"""Simplified FMCSA hours-of-service schedule for property-carrying drivers.

Rest stops shift when the truck reaches later checkpoints, and therefore which
forecast hour applies there. Modelled rules:

- a 30-minute break after 8 hours of cumulative driving;
- 10 consecutive hours off duty after 11 hours of driving, which also resets
  the 8-hour break clock.

Not modelled: the 14-hour on-duty window, 60/70-hour weekly limits and the
sleeper-berth split. A stop is only scheduled if driving remains after it.
"""

from dataclasses import dataclass
from enum import StrEnum

HOUR_S = 3_600.0
BREAK_AFTER_DRIVING_S = 8 * HOUR_S
BREAK_DURATION_S = 0.5 * HOUR_S
MAX_DRIVING_PER_SHIFT_S = 11 * HOUR_S
OFF_DUTY_DURATION_S = 10 * HOUR_S


class StopKind(StrEnum):
    BREAK = "break"
    REST = "rest"


@dataclass(frozen=True, slots=True)
class Stop:
    kind: StopKind
    driving_offset_s: float
    """Cumulative driving time at which the stop begins."""
    duration_s: float


@dataclass(frozen=True, slots=True)
class DrivingSchedule:
    total_driving_s: float
    stops: tuple[Stop, ...]

    @classmethod
    def plan(cls, total_driving_s: float, *, enforce_hos: bool = True) -> "DrivingSchedule":
        if total_driving_s < 0:
            raise ValueError(f"Driving time cannot be negative, got {total_driving_s}.")
        if not enforce_hos:
            return cls(total_driving_s, ())

        stops: list[Stop] = []
        shift_start = 0.0
        while shift_start + BREAK_AFTER_DRIVING_S < total_driving_s:
            stops.append(
                Stop(StopKind.BREAK, shift_start + BREAK_AFTER_DRIVING_S, BREAK_DURATION_S)
            )
            shift_end = shift_start + MAX_DRIVING_PER_SHIFT_S
            if shift_end >= total_driving_s:
                break
            stops.append(Stop(StopKind.REST, shift_end, OFF_DUTY_DURATION_S))
            shift_start = shift_end
        return cls(total_driving_s, tuple(stops))

    def elapsed_at(self, driving_s: float) -> float:
        """Wall-clock time since departure when `driving_s` of driving is done.

        A stop starting exactly at `driving_s` has not happened yet: the truck
        reaches that point first, then stops.
        """
        return driving_s + sum(s.duration_s for s in self.stops if s.driving_offset_s < driving_s)

    @property
    def total_elapsed_s(self) -> float:
        return self.elapsed_at(self.total_driving_s)
