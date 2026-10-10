"""Provider wiring for the API. Tests replace these factories with fakes."""

from functools import cache

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from trips.providers.base import Geocoder
from trips.providers.open_meteo import OpenMeteoProvider
from trips.providers.tomtom import TomTomGeocoder, TomTomRouter
from trips.services.heatmap import HeatmapBuilder
from trips.services.plan_trip import TripPlanner


def _tomtom_key() -> str:
    key: str = settings.TOMTOM_API_KEY
    if not key:
        raise ImproperlyConfigured("TOMTOM_API_KEY is not set.")
    return key


@cache
def get_weather_provider() -> OpenMeteoProvider:
    """One instance per process so trip plans and heatmaps share its forecast cache."""
    return OpenMeteoProvider()


@cache
def get_trip_planner() -> TripPlanner:
    return TripPlanner(TomTomRouter(_tomtom_key()), get_weather_provider())


@cache
def get_geocoder() -> Geocoder:
    return TomTomGeocoder(_tomtom_key())


@cache
def get_heatmap_builder() -> HeatmapBuilder:
    return HeatmapBuilder(get_weather_provider())
