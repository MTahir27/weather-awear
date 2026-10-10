import pytest

from trips.domain.eta import TimeProfile

# 0-10 km in 10 min (city), then 10-110 km in 60 min (highway).
PROFILE = TimeProfile.from_anchors([(0, 0), (10_000, 600), (110_000, 4_200)])


def test_totals() -> None:
    assert PROFILE.total_distance_m == 110_000
    assert PROFILE.total_seconds == 4_200


@pytest.mark.parametrize(
    ("distance_m", "expected_s"),
    [
        (0, 0),
        (5_000, 300),  # halfway through the slow city stretch
        (10_000, 600),  # exactly on an anchor
        (60_000, 2_400),  # halfway through the highway stretch
        (110_000, 4_200),
    ],
)
def test_interpolates_between_anchors(distance_m: float, expected_s: float) -> None:
    assert PROFILE.seconds_at(distance_m) == pytest.approx(expected_s)


def test_uses_segment_speed_not_route_average() -> None:
    # A route-average speed would put 5 km at 4200 * 5/110 = ~191 s.
    assert PROFILE.seconds_at(5_000) == pytest.approx(300)


def test_clamps_outside_the_route() -> None:
    assert PROFILE.seconds_at(-100) == 0
    assert PROFILE.seconds_at(1e9) == 4_200


def test_repeated_distance_keeps_latest_time() -> None:
    profile = TimeProfile.from_anchors([(0, 0), (1_000, 60), (1_000, 360), (2_000, 420)])

    assert profile.distances_m == (0, 1_000, 2_000)
    assert profile.seconds_at(1_500) == pytest.approx(390)


def test_single_anchor_profile_for_zero_length_route() -> None:
    profile = TimeProfile.from_anchors([(0, 0)])

    assert profile.seconds_at(0) == 0
    assert profile.seconds_at(50) == 0


@pytest.mark.parametrize(
    ("anchors", "message"),
    [
        ([], "non-empty"),
        ([(5, 0), (10, 10)], "start at distance 0"),
        ([(0, 3), (10, 10)], "start at distance 0"),
        ([(0, 0), (10, 10), (5, 20)], "strictly increasing"),
        ([(0, 0), (10, 10), (20, 5)], "cannot decrease"),
    ],
)
def test_rejects_invalid_profiles(anchors: list[tuple[float, float]], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        TimeProfile.from_anchors(anchors)


def test_rejects_mismatched_series() -> None:
    with pytest.raises(ValueError, match="matching"):
        TimeProfile((0.0, 1.0), (0.0,))
