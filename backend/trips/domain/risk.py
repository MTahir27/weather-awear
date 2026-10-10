"""Weather risk classification for a single checkpoint.

Thresholds follow the assessment's risk table. The table's ranges touch at
their edges (e.g. rain "0.10-0.25" and "0.25-0.50"), so every boundary value is
assigned to the *higher* level, except where the table explicitly uses a strict
inequality for No Travel (rain "> 1.00", snow "> 3.0"), in which case the
boundary value itself stays Severe.

Wind is classified on sustained wind speed. Load rules can only escalate the
wind level, never lower it.
"""

from dataclasses import dataclass
from enum import IntEnum, StrEnum


class RiskLevel(IntEnum):
    """Ordered risk levels. The integer value is the score used for averages."""

    LOW = 0
    MODERATE = 1
    HIGH = 2
    SEVERE = 3
    NO_TRAVEL = 4


class Factor(StrEnum):
    WIND = "wind"
    RAIN = "rain"
    SNOW = "snow"


@dataclass(frozen=True, slots=True)
class Threshold:
    """Values at or above `value` (or strictly above, if not inclusive) reach `level`."""

    value: float
    level: RiskLevel
    inclusive: bool = True

    def reached_by(self, measurement: float) -> bool:
        return measurement >= self.value if self.inclusive else measurement > self.value


# Ordered from lowest to highest level.
WIND_MPH_THRESHOLDS = (
    Threshold(25, RiskLevel.MODERATE),
    Threshold(35, RiskLevel.HIGH),
    Threshold(45, RiskLevel.SEVERE),
    Threshold(55, RiskLevel.NO_TRAVEL),
)
RAIN_IN_PER_HR_THRESHOLDS = (
    Threshold(0.10, RiskLevel.MODERATE),
    Threshold(0.25, RiskLevel.HIGH),
    Threshold(0.50, RiskLevel.SEVERE),
    Threshold(1.00, RiskLevel.NO_TRAVEL, inclusive=False),
)
SNOW_IN_PER_HR_THRESHOLDS = (
    Threshold(0.5, RiskLevel.MODERATE),
    Threshold(1.0, RiskLevel.HIGH),
    Threshold(2.0, RiskLevel.SEVERE),
    Threshold(3.0, RiskLevel.NO_TRAVEL, inclusive=False),
)

# Load rules, applied to the wind level band.
NO_TRAVEL_IN_SEVERE_WIND_ABOVE_LB = 30_000
SEVERE_IN_HIGH_WIND_ABOVE_LB = 40_000

# Measurements are rounded before comparison so floating-point noise from unit
# conversion or summing (0.07 + 0.03 == 0.09999999999999999) cannot drop a
# value below a threshold it actually meets.
_PRECISION = 6


@dataclass(frozen=True, slots=True)
class WeatherSample:
    """Conditions the truck meets at a checkpoint. `None` means data is unavailable."""

    wind_mph: float | None
    rain_in_per_hr: float | None
    snow_in_per_hr: float | None
    gust_mph: float | None = None


@dataclass(frozen=True, slots=True)
class FactorRisk:
    factor: Factor
    value: float
    level: RiskLevel


@dataclass(frozen=True, slots=True)
class RiskAssessment:
    """Risk at one checkpoint. `level` is `None` when weather data is missing."""

    level: RiskLevel | None
    factors: tuple[FactorRisk, ...]
    load_escalated: bool = False

    @property
    def is_known(self) -> bool:
        return self.level is not None

    @property
    def drivers(self) -> tuple[FactorRisk, ...]:
        """Factors responsible for the overall level (empty when the level is Low)."""
        if self.level is None or self.level == RiskLevel.LOW:
            return ()
        return tuple(f for f in self.factors if f.level == self.level)


def level_for(measurement: float, thresholds: tuple[Threshold, ...]) -> RiskLevel:
    if measurement < 0:
        raise ValueError(f"Weather measurements cannot be negative, got {measurement}.")
    value = round(measurement, _PRECISION)
    level = RiskLevel.LOW
    for threshold in thresholds:
        if threshold.reached_by(value):
            level = threshold.level
    return level


def wind_level(wind_mph: float, load_lb: float) -> tuple[RiskLevel, bool]:
    """Wind level after load rules, and whether the load escalated it.

    - >= 55 mph is No Travel for any load (already the base level).
    - 45-54 mph with a load > 30,000 lb is No Travel.
    - 35-44 mph with a load > 40,000 lb is Severe.
    """
    base = level_for(wind_mph, WIND_MPH_THRESHOLDS)
    if base == RiskLevel.SEVERE and load_lb > NO_TRAVEL_IN_SEVERE_WIND_ABOVE_LB:
        return RiskLevel.NO_TRAVEL, True
    if base == RiskLevel.HIGH and load_lb > SEVERE_IN_HIGH_WIND_ABOVE_LB:
        return RiskLevel.SEVERE, True
    return base, False


def classify(sample: WeatherSample, load_lb: float) -> RiskAssessment:
    """Overall checkpoint risk: the worst of wind (after load rules), rain and snow.

    If any factor is missing the level is unknown rather than assumed Low, so
    missing data can never make a route look safer than it is.
    """
    if load_lb < 0:
        raise ValueError(f"Load weight cannot be negative, got {load_lb}.")
    if sample.wind_mph is None or sample.rain_in_per_hr is None or sample.snow_in_per_hr is None:
        return RiskAssessment(level=None, factors=())

    wind, _ = wind_level(sample.wind_mph, load_lb)
    rain = level_for(sample.rain_in_per_hr, RAIN_IN_PER_HR_THRESHOLDS)
    snow = level_for(sample.snow_in_per_hr, SNOW_IN_PER_HR_THRESHOLDS)
    factors = (
        FactorRisk(Factor.WIND, sample.wind_mph, wind),
        FactorRisk(Factor.RAIN, sample.rain_in_per_hr, rain),
        FactorRisk(Factor.SNOW, sample.snow_in_per_hr, snow),
    )
    level = max(wind, rain, snow)
    level_without_load = max(level_for(sample.wind_mph, WIND_MPH_THRESHOLDS), rain, snow)
    return RiskAssessment(level=level, factors=factors, load_escalated=level > level_without_load)
