"""Route ranking and recommendation.

Routes are compared lexicographically, following the assessment's priorities:

1. fewest No Travel miles (not in the brief's list, but a route that crosses
   No Travel conditions must never outrank one that does not);
2. fewest Severe miles;
3. fewest High miles;
4. lowest average risk;
5. shortest travel time;
6. shortest distance, then input order, so ties resolve deterministically.

Miles whose weather is unknown count as Severe for ranking. Otherwise a route
with missing forecasts would look safer than one with known bad weather.
Distances are compared at 0.001-mile (~1.6 m) resolution and average risk at
0.001, so floating-point noise cannot decide a ranking while even a very short
No Travel stretch still counts.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from trips.domain.geo import meters_to_miles
from trips.domain.risk import RiskLevel
from trips.domain.scoring import RouteRisk


class DecidingFactor(StrEnum):
    ONLY_ROUTE = "only_route"
    NO_TRAVEL_MILES = "no_travel_miles"
    SEVERE_MILES = "severe_miles"
    HIGH_MILES = "high_miles"
    AVERAGE_RISK = "average_risk"
    TRAVEL_TIME = "travel_time"
    DISTANCE = "distance"
    TIE = "tie"


@dataclass(frozen=True, slots=True)
class RouteCandidate:
    route_id: str
    risk: RouteRisk
    duration_s: float
    """Door-to-door time, including any hours-of-service stops."""
    distance_m: float

    @property
    def severe_or_unknown_m(self) -> float:
        return self.risk.meters_at(RiskLevel.SEVERE) + self.risk.unknown_m

    @property
    def ranking_average(self) -> float:
        """Average risk with unknown stretches scored as Severe."""
        total = self.risk.total_m
        if total <= 0:
            return (
                self.risk.average_score
                if self.risk.average_score is not None
                else float(RiskLevel.SEVERE)
            )
        known = sum(int(level) * m for level, m in self.risk.meters_by_level.items())
        return (known + int(RiskLevel.SEVERE) * self.risk.unknown_m) / total


@dataclass(frozen=True, slots=True)
class Recommendation:
    ranked_ids: tuple[str, ...]
    recommended_id: str
    travel_advised: bool
    """False when every route crosses No Travel conditions."""
    deciding_factor: DecidingFactor
    explanation: str


_FACTOR_ORDER = (
    DecidingFactor.NO_TRAVEL_MILES,
    DecidingFactor.SEVERE_MILES,
    DecidingFactor.HIGH_MILES,
    DecidingFactor.AVERAGE_RISK,
    DecidingFactor.TRAVEL_TIME,
    DecidingFactor.DISTANCE,
)


def _miles(meters: float) -> float:
    """Comparison precision: fine enough that no real stretch rounds to zero."""
    return round(meters_to_miles(meters), 3)


def _display_miles(meters: float) -> str:
    return f"{round(meters_to_miles(meters), 1):g}"


def ranking_key(candidate: RouteCandidate) -> tuple[float, ...]:
    risk = candidate.risk
    return (
        _miles(risk.meters_at(RiskLevel.NO_TRAVEL)),
        _miles(candidate.severe_or_unknown_m),
        _miles(risk.meters_at(RiskLevel.HIGH)),
        round(candidate.ranking_average, 3),
        round(candidate.duration_s),
        _miles(candidate.distance_m),
    )


def recommend(candidates: Sequence[RouteCandidate]) -> Recommendation:
    if not candidates:
        raise ValueError("At least one route is required.")
    if len({c.route_id for c in candidates}) != len(candidates):
        raise ValueError("Route ids must be unique.")

    # sorted() is stable, so equal keys keep the provider's order.
    ranked = sorted(candidates, key=ranking_key)
    best = ranked[0]
    travel_advised = best.risk.meters_at(RiskLevel.NO_TRAVEL) == 0

    if len(ranked) == 1:
        factor = DecidingFactor.ONLY_ROUTE
        explanation = "This is the only route available."
    else:
        factor = _deciding_factor(best, ranked[1])
        explanation = _explain(factor, best, ranked[1])

    if not travel_advised:
        explanation = (
            "Every route crosses No Travel conditions at this departure time. "
            "This is the least risky option; consider departing at a different time. " + explanation
        )

    return Recommendation(
        ranked_ids=tuple(c.route_id for c in ranked),
        recommended_id=best.route_id,
        travel_advised=travel_advised,
        deciding_factor=factor,
        explanation=explanation,
    )


def _deciding_factor(best: RouteCandidate, runner_up: RouteCandidate) -> DecidingFactor:
    for factor, a, b in zip(_FACTOR_ORDER, ranking_key(best), ranking_key(runner_up), strict=True):
        if a != b:
            return factor
    return DecidingFactor.TIE


def _explain(factor: DecidingFactor, best: RouteCandidate, other: RouteCandidate) -> str:
    def vs(a_m: float, b_m: float) -> str:
        return f"{_display_miles(a_m)} mi vs {_display_miles(b_m)} mi on the next best route"

    match factor:
        case DecidingFactor.NO_TRAVEL_MILES:
            a = best.risk.meters_at(RiskLevel.NO_TRAVEL)
            b = other.risk.meters_at(RiskLevel.NO_TRAVEL)
            return f"Fewest No Travel miles ({vs(a, b)})."
        case DecidingFactor.SEVERE_MILES:
            note = (
                " Miles without forecast data count as Severe."
                if best.risk.unknown_m or other.risk.unknown_m
                else ""
            )
            return (
                f"Fewest Severe miles ({vs(best.severe_or_unknown_m, other.severe_or_unknown_m)})."
                + note
            )
        case DecidingFactor.HIGH_MILES:
            a = best.risk.meters_at(RiskLevel.HIGH)
            b = other.risk.meters_at(RiskLevel.HIGH)
            return f"Same Severe exposure; fewest High-risk miles ({vs(a, b)})."
        case DecidingFactor.AVERAGE_RISK:
            return (
                "Same Severe and High exposure; lowest average risk "
                f"({best.ranking_average:.2f} vs {other.ranking_average:.2f})."
            )
        case DecidingFactor.TRAVEL_TIME:
            minutes = round((other.duration_s - best.duration_s) / 60)
            return f"Same weather risk; fastest route ({_format_minutes(minutes)} sooner)."
        case DecidingFactor.DISTANCE:
            return "Same weather risk and travel time; shortest distance."
        case _:
            return "Equivalent to the alternatives on weather risk, travel time and distance."


def _format_minutes(minutes: int) -> str:
    hours, mins = divmod(minutes, 60)
    if hours and mins:
        return f"{hours} h {mins} min"
    if hours:
        return f"{hours} h"
    return f"{mins} min"
