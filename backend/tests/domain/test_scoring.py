import pytest

from trips.domain.risk import RiskLevel
from trips.domain.scoring import CheckpointLevel, score_route, stretch_lengths_m

L, M, H, S, NT = (
    RiskLevel.LOW,
    RiskLevel.MODERATE,
    RiskLevel.HIGH,
    RiskLevel.SEVERE,
    RiskLevel.NO_TRAVEL,
)


def route(levels: list[RiskLevel | None], spacing: float = 10.0) -> list[CheckpointLevel]:
    return [CheckpointLevel(i * spacing, level) for i, level in enumerate(levels)]


class TestStretchLengths:
    def test_uniform_spacing(self) -> None:
        # Ends own half an interval, interior checkpoints a full interval.
        assert stretch_lengths_m([0, 10, 20, 30], 30) == [5, 10, 10, 5]

    def test_short_final_interval_carries_less_weight(self) -> None:
        assert stretch_lengths_m([0, 25, 50, 60], 60) == [12.5, 25, 17.5, 5]

    def test_lengths_always_sum_to_route_length(self) -> None:
        distances = [0, 7, 19, 33, 41.5]

        assert sum(stretch_lengths_m(distances, 41.5)) == pytest.approx(41.5)

    def test_single_checkpoint_owns_whole_route(self) -> None:
        assert stretch_lengths_m([0], 0) == [0]

    @pytest.mark.parametrize(
        ("distances", "total", "message"),
        [
            ([], 10, "At least one"),
            ([0, 20, 10], 20, "ordered"),
            ([-1, 10], 10, "within the route"),
            ([0, 15], 10, "within the route"),
        ],
    )
    def test_rejects_invalid_checkpoints(
        self, distances: list[float], total: float, message: str
    ) -> None:
        with pytest.raises(ValueError, match=message):
            stretch_lengths_m(distances, total)


class TestScoreRoute:
    def test_all_low(self) -> None:
        result = score_route(route([L, L, L]), 20)

        assert result.meters_at(L) == 20
        assert result.meters_at(S) == 0
        assert result.average_score == 0
        assert result.worst_level == L
        assert result.unknown_m == 0

    def test_distance_per_level(self) -> None:
        # Stretches: 5, 10, 10, 5
        result = score_route(route([L, S, H, S]), 30)

        assert result.meters_at(L) == 5
        assert result.meters_at(H) == 10
        assert result.meters_at(S) == 15
        assert result.worst_level == S

    def test_average_is_distance_weighted(self) -> None:
        # Stretches 12.5 (Low), 25 (Low), 17.5 (Low), 5 (No Travel).
        result = score_route(
            [CheckpointLevel(d, lvl) for d, lvl in [(0, L), (25, L), (50, L), (60, NT)]], 60
        )

        assert result.average_score == pytest.approx(4 * 5 / 60)

    def test_unknown_stretches_are_reported_separately(self) -> None:
        result = score_route(route([L, None, M]), 20)

        assert result.unknown_m == 10
        assert result.meters_at(L) == 5
        assert result.meters_at(M) == 5
        assert result.average_score == pytest.approx(0.5)
        assert result.worst_level == M

    def test_all_unknown(self) -> None:
        result = score_route(route([None, None]), 10)

        assert result.unknown_m == 10
        assert result.average_score is None
        assert result.worst_level is None

    def test_zero_length_route_uses_unweighted_average(self) -> None:
        result = score_route([CheckpointLevel(0, H)], 0)

        assert result.average_score == 2
        assert result.worst_level == H
