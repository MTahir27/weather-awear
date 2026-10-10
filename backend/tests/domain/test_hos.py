import pytest

from trips.domain.hos import DrivingSchedule, Stop, StopKind

H = 3_600.0


def kinds_and_offsets(schedule: DrivingSchedule) -> list[tuple[StopKind, float]]:
    return [(s.kind, s.driving_offset_s / H) for s in schedule.stops]


def test_short_trip_needs_no_stops() -> None:
    schedule = DrivingSchedule.plan(5 * H)

    assert schedule.stops == ()
    assert schedule.total_elapsed_s == 5 * H


def test_exactly_eight_hours_needs_no_break() -> None:
    assert DrivingSchedule.plan(8 * H).stops == ()


def test_break_after_eight_hours_of_driving() -> None:
    schedule = DrivingSchedule.plan(10 * H)

    assert schedule.stops == (Stop(StopKind.BREAK, 8 * H, 0.5 * H),)
    assert schedule.total_elapsed_s == 10.5 * H


def test_exactly_eleven_hours_needs_no_rest() -> None:
    schedule = DrivingSchedule.plan(11 * H)

    assert kinds_and_offsets(schedule) == [(StopKind.BREAK, 8)]
    assert schedule.total_elapsed_s == 11.5 * H


def test_long_trip_alternates_breaks_and_rests() -> None:
    # Dallas -> Chicago class trip: 14 h of driving.
    schedule = DrivingSchedule.plan(14 * H)

    assert kinds_and_offsets(schedule) == [(StopKind.BREAK, 8), (StopKind.REST, 11)]
    assert schedule.total_elapsed_s == (14 + 0.5 + 10) * H


def test_rest_resets_the_break_clock() -> None:
    # After each 10 h rest the next break is due 8 h into the new shift.
    schedule = DrivingSchedule.plan(31 * H)

    assert kinds_and_offsets(schedule) == [
        (StopKind.BREAK, 8),
        (StopKind.REST, 11),
        (StopKind.BREAK, 19),
        (StopKind.REST, 22),
        (StopKind.BREAK, 30),
    ]
    assert schedule.total_elapsed_s == (31 + 3 * 0.5 + 2 * 10) * H


@pytest.mark.parametrize(
    ("driving_h", "elapsed_h"),
    [
        (0, 0),
        (8, 8),  # arrives at the break point before taking the break
        (8.5, 9),
        (11, 11.5),  # arrives at the rest point before resting
        (12, 22.5),
    ],
)
def test_elapsed_time_includes_stops_already_taken(driving_h: float, elapsed_h: float) -> None:
    schedule = DrivingSchedule.plan(14 * H)

    assert schedule.elapsed_at(driving_h * H) == pytest.approx(elapsed_h * H)


def test_hos_can_be_disabled() -> None:
    schedule = DrivingSchedule.plan(30 * H, enforce_hos=False)

    assert schedule.stops == ()
    assert schedule.elapsed_at(20 * H) == 20 * H


def test_negative_driving_time_is_rejected() -> None:
    with pytest.raises(ValueError, match="cannot be negative"):
        DrivingSchedule.plan(-1)
