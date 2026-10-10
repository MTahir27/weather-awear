import pytest

from trips.domain.geo import LatLon, cumulative_distances_m, miles_to_meters
from trips.domain.sampling import checkpoint_offsets_m, sample_checkpoints

MILE = miles_to_meters(1)


def as_miles(offsets: list[float]) -> list[float]:
    return [round(o / MILE, 6) for o in offsets]


@pytest.mark.parametrize(
    ("total_mi", "interval_mi", "expected_mi"),
    [
        (60, 25, [0, 25, 50, 60]),
        (50, 25, [0, 25, 50]),  # exact multiple: no duplicate destination
        (10, 25, [0, 10]),  # shorter than one interval
        (101, 50, [0, 50, 100, 101]),
        (35, 10, [0, 10, 20, 30, 35]),
    ],
)
def test_offsets_include_origin_every_interval_and_destination(
    total_mi: float, interval_mi: float, expected_mi: list[float]
) -> None:
    offsets = checkpoint_offsets_m(miles_to_meters(total_mi), miles_to_meters(interval_mi))

    assert as_miles(offsets) == expected_mi


def test_zero_length_route_has_single_checkpoint() -> None:
    assert checkpoint_offsets_m(0, MILE) == [0]


def test_tail_within_tolerance_is_not_duplicated() -> None:
    offsets = checkpoint_offsets_m(miles_to_meters(50) + 0.5, miles_to_meters(25))

    assert len(offsets) == 3
    assert offsets[-1] == pytest.approx(miles_to_meters(50) + 0.5)


def test_long_route_has_no_floating_point_drift() -> None:
    offsets = checkpoint_offsets_m(miles_to_meters(3000), miles_to_meters(10))

    assert len(offsets) == 301
    assert offsets[150] == miles_to_meters(10) * 150


@pytest.mark.parametrize(
    ("total", "interval", "message"),
    [
        (-1, MILE, "cannot be negative"),
        (MILE, 0, "must be positive"),
        (MILE, -5, "must be positive"),
    ],
)
def test_invalid_inputs_are_rejected(total: float, interval: float, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        checkpoint_offsets_m(total, interval)


def test_sample_checkpoints_positions_follow_the_polyline() -> None:
    # Due north along a meridian: ~69 miles per degree of latitude.
    points = [LatLon(0, 0), LatLon(1, 0), LatLon(2, 0)]
    cumulative = cumulative_distances_m(points)

    checkpoints = sample_checkpoints(points, cumulative, cumulative[-1] / 4)

    assert [c.index for c in checkpoints] == [0, 1, 2, 3, 4]
    assert checkpoints[0].position == points[0]
    assert checkpoints[-1].position == points[-1]
    assert checkpoints[-1].distance_m == cumulative[-1]
    assert [round(c.position.lat, 6) for c in checkpoints] == [0, 0.5, 1, 1.5, 2]
