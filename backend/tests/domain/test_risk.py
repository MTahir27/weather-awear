import pytest

from trips.domain.risk import (
    RAIN_IN_PER_HR_THRESHOLDS,
    SNOW_IN_PER_HR_THRESHOLDS,
    WIND_MPH_THRESHOLDS,
    Factor,
    RiskLevel,
    WeatherSample,
    classify,
    level_for,
    wind_level,
)

L, M, H, S, NT = (
    RiskLevel.LOW,
    RiskLevel.MODERATE,
    RiskLevel.HIGH,
    RiskLevel.SEVERE,
    RiskLevel.NO_TRAVEL,
)
LIGHT_LOAD = 10_000


def calm(**overrides: float) -> WeatherSample:
    values = {"wind_mph": 5.0, "rain_in_per_hr": 0.0, "snow_in_per_hr": 0.0} | overrides
    return WeatherSample(**values)


@pytest.mark.parametrize(
    ("mph", "expected"),
    [
        (0, L),
        (24.99, L),
        (25, M),
        (34, M),
        (34.99, M),  # between the table's integer ranges "25-34" and "35-44"
        (35, H),
        (44.6, H),
        (45, S),
        (54.99, S),
        (55, NT),
        (80, NT),
    ],
)
def test_wind_thresholds(mph: float, expected: RiskLevel) -> None:
    assert level_for(mph, WIND_MPH_THRESHOLDS) == expected


@pytest.mark.parametrize(
    ("inches", "expected"),
    [
        (0, L),
        (0.099, L),
        (0.10, M),
        (0.249, M),
        (0.25, H),  # shared edge of "0.10-0.25" and "0.25-0.50" goes up
        (0.50, S),
        (0.999, S),
        (1.00, S),  # No Travel is strictly "> 1.00"
        (1.001, NT),
    ],
)
def test_rain_thresholds(inches: float, expected: RiskLevel) -> None:
    assert level_for(inches, RAIN_IN_PER_HR_THRESHOLDS) == expected


@pytest.mark.parametrize(
    ("inches", "expected"),
    [
        (0, L),
        (0.49, L),
        (0.5, M),
        (1.0, H),
        (1.99, H),
        (2.0, S),
        (3.0, S),  # No Travel is strictly "> 3.0"
        (3.01, NT),
    ],
)
def test_snow_thresholds(inches: float, expected: RiskLevel) -> None:
    assert level_for(inches, SNOW_IN_PER_HR_THRESHOLDS) == expected


def test_floating_point_noise_does_not_drop_below_threshold() -> None:
    summed = 0.07 + 0.03  # 0.09999999999999999

    assert level_for(summed, RAIN_IN_PER_HR_THRESHOLDS) == M


def test_negative_measurement_is_rejected() -> None:
    with pytest.raises(ValueError, match="cannot be negative"):
        level_for(-0.1, RAIN_IN_PER_HR_THRESHOLDS)


@pytest.mark.parametrize(
    ("mph", "load_lb", "expected", "escalated"),
    [
        # >= 55 mph is No Travel for any load.
        (55, 0, NT, False),
        (60, 80_000, NT, False),
        # 45-54 mph: No Travel only for loads strictly above 30,000 lb.
        (45, 30_000, S, False),
        (45, 30_001, NT, True),
        (54.9, 45_000, NT, True),
        # 35-44 mph: Severe only for loads strictly above 40,000 lb.
        (35, 40_000, H, False),
        (35, 40_001, S, True),
        (44.9, 80_000, S, True),
        # Below 35 mph the load never matters.
        (34.9, 80_000, M, False),
        (10, 80_000, L, False),
    ],
)
def test_wind_load_rules(mph: float, load_lb: int, expected: RiskLevel, escalated: bool) -> None:
    assert wind_level(mph, load_lb) == (expected, escalated)


class TestClassify:
    def test_calm_weather_is_low_with_no_drivers(self) -> None:
        result = classify(calm(), LIGHT_LOAD)

        assert result.level == L
        assert result.is_known
        assert result.drivers == ()
        assert not result.load_escalated

    def test_overall_level_is_the_worst_factor(self) -> None:
        result = classify(calm(wind_mph=26, rain_in_per_hr=0.3, snow_in_per_hr=0.6), LIGHT_LOAD)

        assert result.level == H
        assert [d.factor for d in result.drivers] == [Factor.RAIN]

    def test_reports_every_factor_tied_for_worst(self) -> None:
        result = classify(calm(wind_mph=36, rain_in_per_hr=0.3), LIGHT_LOAD)

        assert result.level == H
        assert {d.factor for d in result.drivers} == {Factor.WIND, Factor.RAIN}

    def test_heavy_load_escalates_wind_to_no_travel(self) -> None:
        result = classify(calm(wind_mph=47), 38_000)

        assert result.level == NT
        assert result.load_escalated
        assert result.drivers[0].factor == Factor.WIND

    def test_escalation_not_flagged_when_another_factor_already_sets_the_level(self) -> None:
        # Wind 36 mph + 45,000 lb -> Severe, but heavy rain is already Severe.
        result = classify(calm(wind_mph=36, rain_in_per_hr=0.6), 45_000)

        assert result.level == S
        assert not result.load_escalated

    @pytest.mark.parametrize("missing", ["wind_mph", "rain_in_per_hr", "snow_in_per_hr"])
    def test_missing_data_is_unknown_not_low(self, missing: str) -> None:
        sample = WeatherSample(
            **{"wind_mph": 5.0, "rain_in_per_hr": 0.0, "snow_in_per_hr": 0.0, missing: None}
        )

        result = classify(sample, LIGHT_LOAD)

        assert result.level is None
        assert not result.is_known
        assert result.drivers == ()

    def test_gusts_do_not_affect_classification(self) -> None:
        result = classify(WeatherSample(20, 0, 0, gust_mph=60), LIGHT_LOAD)

        assert result.level == L

    def test_negative_load_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="Load weight"):
            classify(calm(), -1)
