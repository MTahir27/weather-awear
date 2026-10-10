from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from tests.services.test_plan_trip import HOUR, weather
from trips.domain.geo import LatLon
from trips.domain.risk import RiskLevel
from trips.services.heatmap import UNKNOWN_LEVEL, HeatmapBuilder, HeatmapRequest

DEPART = datetime(2030, 3, 1, 8, 30, tzinfo=UTC)
ROUTE = [LatLon(40, -100), LatLon(40, -99)]


BASE_REQUEST = HeatmapRequest(routes=[ROUTE], depart_at=DEPART, load_lb=20_000, hours=48)


def request(**overrides: Any) -> HeatmapRequest:
    return replace(BASE_REQUEST, **overrides)


def test_builds_one_frame_per_hour_including_departure() -> None:
    fake = weather()

    heatmap = HeatmapBuilder(fake).build(request())

    assert heatmap.frame_count == 49
    assert len(heatmap.points) > 0
    assert all(len(frame) == len(heatmap.points) for frame in heatmap.risk)
    assert all(len(frame) == len(heatmap.points) for frame in heatmap.wind_mph)
    # One batched forecast request spanning the whole window.
    assert len(fake.calls) == 1
    assert fake.calls[0]["start"] == DEPART
    assert fake.calls[0]["end"] == DEPART + timedelta(hours=48)


def test_frames_follow_the_forecast_over_time() -> None:
    storm_from = int(DEPART.timestamp()) + 6 * HOUR

    def storm_later(location: LatLon, t: int) -> tuple[float, float, float]:
        return (5.0, 0.6, 0.0) if t > storm_from else (5.0, 0.0, 0.0)

    heatmap = HeatmapBuilder(weather(storm_later)).build(request())

    assert set(heatmap.risk[0]) == {int(RiskLevel.LOW)}
    assert set(heatmap.risk[10]) == {int(RiskLevel.SEVERE)}
    assert heatmap.rain_in_per_hr[10][0] == pytest.approx(0.6)


def test_load_rules_apply_to_heatmap_risk() -> None:
    def windy(location: LatLon, t: int) -> tuple[float, float, float]:
        return (47.0, 0.0, 0.0)

    light = HeatmapBuilder(weather(windy)).build(request(load_lb=30_000))
    heavy = HeatmapBuilder(weather(windy)).build(request(load_lb=30_001))

    assert set(light.risk[0]) == {int(RiskLevel.SEVERE)}
    assert set(heavy.risk[0]) == {int(RiskLevel.NO_TRAVEL)}


def test_hours_beyond_the_forecast_are_unknown() -> None:
    heatmap = HeatmapBuilder(weather(hours_available=3)).build(request())

    assert UNKNOWN_LEVEL not in heatmap.risk[0]
    assert set(heatmap.risk[48]) == {UNKNOWN_LEVEL}
    assert heatmap.wind_mph[48][0] is None


def test_no_routes_gives_empty_frames_without_fetching() -> None:
    fake = weather()

    heatmap = HeatmapBuilder(fake).build(request(routes=[]))

    assert heatmap.points == ()
    assert heatmap.frame_count == 49
    assert fake.calls == []
