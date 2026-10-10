from typing import Any

import pytest

from trips.domain.forecast import UNKNOWN, HourlySeries

H = 3_600
T0 = 1_800_000_000 - (1_800_000_000 % H)  # an exact hour


def series(**overrides: tuple[float | None, ...]) -> HourlySeries:
    values: dict[str, tuple[float | None, ...]] = {
        "wind_mph": (10.0, 20.0, 40.0),
        "gust_mph": (15.0, 30.0, 60.0),
        "rain_in": (0.0, 0.2, 0.6),
        "snow_in": (0.0, 0.0, 1.5),
    } | overrides
    return HourlySeries(times=(T0, T0 + H, T0 + 2 * H), **values)


def test_exact_hour_uses_that_hours_values() -> None:
    sample = series().sample_at(T0 + H)

    assert sample.wind_mph == 20
    assert sample.gust_mph == 30
    assert sample.rain_in_per_hr == 0.2
    assert sample.snow_in_per_hr == 0


def test_precipitation_uses_the_hour_ending_after_arrival() -> None:
    # Arrival at T0+1h20m falls in the hour ending at T0+2h.
    sample = series().sample_at(T0 + H + 20 * 60)

    assert sample.rain_in_per_hr == 0.6
    assert sample.snow_in_per_hr == 1.5


def test_wind_is_interpolated_between_hours() -> None:
    sample = series().sample_at(T0 + H + 30 * 60)

    assert sample.wind_mph == pytest.approx(30)
    assert sample.gust_mph == pytest.approx(45)


def test_first_hour_is_valid() -> None:
    sample = series().sample_at(T0)

    assert sample.wind_mph == 10
    assert sample.rain_in_per_hr == 0


@pytest.mark.parametrize("offset", [-1, 2 * H + 1])
def test_outside_forecast_is_unknown(offset: int) -> None:
    assert series().sample_at(T0 + offset) == UNKNOWN


def test_missing_values_stay_missing() -> None:
    sample = series(wind_mph=(10.0, None, 40.0), rain_in=(0.0, None, 0.6)).sample_at(T0 + 30 * 60)

    assert sample.wind_mph is None
    assert sample.rain_in_per_hr is None
    assert sample.snow_in_per_hr == 0


def test_start_and_end() -> None:
    assert (series().start, series().end) == (T0, T0 + 2 * H)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"times": ()}, "at least one hour"),
        ({"wind_mph": (1.0,)}, "one value per hour"),
        ({"times": (T0, T0, T0 + H)}, "strictly increasing"),
    ],
)
def test_rejects_invalid_series(kwargs: dict[str, Any], message: str) -> None:
    values: dict[str, Any] = {
        "times": (T0, T0 + H, T0 + 2 * H),
        "wind_mph": (1.0, 1.0, 1.0),
        "gust_mph": (1.0, 1.0, 1.0),
        "rain_in": (0.0, 0.0, 0.0),
        "snow_in": (0.0, 0.0, 0.0),
    } | kwargs
    with pytest.raises(ValueError, match=message):
        HourlySeries(**values)
