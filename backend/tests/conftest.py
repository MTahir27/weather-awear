from collections.abc import Iterator

import pytest
from django.core.cache import cache

from trips.api import dependencies


@pytest.fixture(autouse=True)
def isolated_state() -> Iterator[None]:
    """Each test starts with empty caches (throttle counters, geocode results, providers)."""
    cache.clear()
    dependencies.get_trip_planner.cache_clear()
    dependencies.get_geocoder.cache_clear()
    dependencies.get_heatmap_builder.cache_clear()
    dependencies.get_weather_provider.cache_clear()
    yield
    cache.clear()
