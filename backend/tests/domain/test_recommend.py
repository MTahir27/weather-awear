import pytest

from trips.domain.geo import miles_to_meters
from trips.domain.recommend import (
    DecidingFactor,
    RouteCandidate,
    ranking_key,
    recommend,
)
from trips.domain.risk import RiskLevel
from trips.domain.scoring import RouteRisk

L, M, H, S, NT = (
    RiskLevel.LOW,
    RiskLevel.MODERATE,
    RiskLevel.HIGH,
    RiskLevel.SEVERE,
    RiskLevel.NO_TRAVEL,
)
HOUR = 3_600.0


def candidate(
    route_id: str,
    *,
    miles: dict[RiskLevel, float] | None = None,
    unknown_mi: float = 0,
    hours: float = 10,
    total_mi: float | None = None,
) -> RouteCandidate:
    per_level = {level: miles_to_meters(m) for level, m in (miles or {L: 100}).items()}
    unknown_m = miles_to_meters(unknown_mi)
    total_m = (
        miles_to_meters(total_mi) if total_mi is not None else sum(per_level.values()) + unknown_m
    )
    known_m = sum(per_level.values())
    average = sum(int(lvl) * m for lvl, m in per_level.items()) / known_m if known_m else None
    risk = RouteRisk(
        total_m=total_m,
        meters_by_level=per_level,
        unknown_m=unknown_m,
        average_score=average,
        worst_level=max(per_level) if per_level else None,
    )
    return RouteCandidate(route_id, risk, duration_s=hours * HOUR, distance_m=total_m)


def test_single_route() -> None:
    result = recommend([candidate("a")])

    assert result.recommended_id == "a"
    assert result.deciding_factor == DecidingFactor.ONLY_ROUTE
    assert result.travel_advised


def test_fewest_severe_miles_beats_faster_route() -> None:
    risky_fast = candidate("fast", miles={L: 90, S: 10}, hours=8)
    safe_slow = candidate("safe", miles={L: 100}, hours=12)

    result = recommend([risky_fast, safe_slow])

    assert result.ranked_ids == ("safe", "fast")
    assert result.deciding_factor == DecidingFactor.SEVERE_MILES
    assert "0 mi vs 10 mi" in result.explanation


def test_no_travel_outranks_any_amount_of_severe() -> None:
    # Spec's list starts at Severe; a No Travel stretch must still lose.
    no_travel = candidate("nt", miles={L: 99, NT: 1})
    lots_of_severe = candidate("sev", miles={L: 20, S: 80})

    result = recommend([no_travel, lots_of_severe])

    assert result.recommended_id == "sev"
    assert result.deciding_factor == DecidingFactor.NO_TRAVEL_MILES
    assert result.travel_advised


def test_high_miles_break_severe_tie() -> None:
    result = recommend([candidate("a", miles={L: 50, H: 50}), candidate("b", miles={L: 80, H: 20})])

    assert result.recommended_id == "b"
    assert result.deciding_factor == DecidingFactor.HIGH_MILES


def test_average_risk_breaks_high_tie() -> None:
    result = recommend([candidate("a", miles={L: 20, M: 80}), candidate("b", miles={L: 80, M: 20})])

    assert result.recommended_id == "b"
    assert result.deciding_factor == DecidingFactor.AVERAGE_RISK


def test_travel_time_breaks_risk_tie() -> None:
    result = recommend([candidate("slow", hours=11.5), candidate("quick", hours=10)])

    assert result.recommended_id == "quick"
    assert result.deciding_factor == DecidingFactor.TRAVEL_TIME
    assert "1 h 30 min sooner" in result.explanation


def test_distance_breaks_time_tie() -> None:
    result = recommend(
        [candidate("long", total_mi=120, miles={L: 120}), candidate("short", miles={L: 100})]
    )

    assert result.recommended_id == "short"
    assert result.deciding_factor == DecidingFactor.DISTANCE


def test_full_tie_keeps_provider_order() -> None:
    result = recommend([candidate("first"), candidate("second")])

    assert result.ranked_ids == ("first", "second")
    assert result.deciding_factor == DecidingFactor.TIE


def test_unknown_miles_count_as_severe() -> None:
    # A route with no forecast data must not look safer than known Severe weather.
    unforecast = candidate("blind", miles={}, unknown_mi=100)
    known_severe = candidate("known", miles={L: 95, S: 5})

    result = recommend([unforecast, known_severe])

    assert result.recommended_id == "known"
    assert "without forecast data count as Severe" in result.explanation


def test_all_routes_blocked_is_flagged_but_still_ranked() -> None:
    result = recommend(
        [candidate("a", miles={L: 90, NT: 10}), candidate("b", miles={L: 97, NT: 3})]
    )

    assert result.recommended_id == "b"
    assert not result.travel_advised
    assert result.explanation.startswith("Every route crosses No Travel")


def test_float_noise_does_not_decide_ranking() -> None:
    a = candidate("a", miles={L: 100.0}, hours=10)
    b = candidate("b", miles={L: 100.0 + 1e-9}, hours=10)

    assert ranking_key(a) == ranking_key(b)


def test_zero_length_route_ranking_average() -> None:
    # score_route falls back to an unweighted average for zero-length routes.
    known = RouteCandidate("known", RouteRisk(total_m=0, average_score=2), 0, 0)
    blind = RouteCandidate("blind", RouteRisk(total_m=0), 0, 0)

    assert known.ranking_average == 2
    assert blind.ranking_average == 3


@pytest.mark.parametrize(
    ("minutes_apart", "text"),
    [(45, "45 min sooner"), (120, "2 h sooner"), (95, "1 h 35 min sooner")],
)
def test_time_formatting(minutes_apart: int, text: str) -> None:
    result = recommend(
        [candidate("slow", hours=10 + minutes_apart / 60), candidate("quick", hours=10)]
    )

    assert text in result.explanation


def test_rejects_empty_and_duplicate_routes() -> None:
    with pytest.raises(ValueError, match="At least one"):
        recommend([])
    with pytest.raises(ValueError, match="unique"):
        recommend([candidate("a"), candidate("a")])
