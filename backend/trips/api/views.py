import hashlib
import logging

from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from rest_framework import status
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from trips.api import dependencies
from trips.api.presenters import present_heatmap, present_plan
from trips.api.serializers import (
    GeocodeQuerySerializer,
    HeatmapRequestSerializer,
    TripRequestSerializer,
)
from trips.providers.base import NoRouteFound
from trips.providers.http import ProviderError, ProviderUnavailable

logger = logging.getLogger(__name__)

GEOCODE_CACHE_SECONDS = 24 * 3600
GEOCODE_LIMIT = 6


# Per-client-IP limits. (ScopedRateThrottle would read the scope from a
# `throttle_scope` view attribute, which function views do not have.)
class PlanThrottle(AnonRateThrottle):
    scope = "plan"


class GeocodeThrottle(AnonRateThrottle):
    scope = "geocode"


class HeatmapThrottle(AnonRateThrottle):
    scope = "heatmap"


@api_view(["GET"])
def health(request: Request) -> Response:
    return Response({"status": "ok"})


def _provider_failure(exc: ProviderError) -> Response:
    logger.warning("Upstream provider failure: %s (status %s)", exc, exc.status_code)
    if exc.status_code == 429:
        detail = (
            f"{exc.provider} is receiving too many requests right now. "
            "Please try again in a minute."
        )
    elif isinstance(exc, ProviderUnavailable):
        detail = f"{exc.provider} is not responding right now. Please try again shortly."
    else:
        detail = f"{exc.provider} returned an unexpected response. Please try again."
    unavailable = isinstance(exc, ProviderUnavailable)
    return Response(
        {"detail": detail},
        status=status.HTTP_503_SERVICE_UNAVAILABLE if unavailable else status.HTTP_502_BAD_GATEWAY,
    )


def _not_configured(exc: ImproperlyConfigured) -> Response:
    logger.error("Service misconfigured: %s", exc)
    return Response(
        {"detail": "The routing service is not configured."},
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


@api_view(["POST"])
@throttle_classes([PlanThrottle])
def plan_trip(request: Request) -> Response:
    serializer = TripRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        plan = dependencies.get_trip_planner().plan(serializer.to_trip_request())
    except NoRouteFound:
        return Response(
            {"detail": "No truck route connects these locations."},
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    except ProviderError as exc:
        return _provider_failure(exc)
    except ImproperlyConfigured as exc:
        return _not_configured(exc)
    return Response(present_plan(plan))


@api_view(["POST"])
@throttle_classes([HeatmapThrottle])
def heatmap(request: Request) -> Response:
    serializer = HeatmapRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        result = dependencies.get_heatmap_builder().build(serializer.to_heatmap_request())
    except ProviderError as exc:
        return _provider_failure(exc)
    return Response(present_heatmap(result))


@api_view(["GET"])
@throttle_classes([GeocodeThrottle])
def geocode(request: Request) -> Response:
    serializer = GeocodeQuerySerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    query = serializer.validated_data["q"]

    # Hash the normalised query: raw text (spaces, any Unicode) is not a portable cache key.
    cache_key = "geocode:" + hashlib.sha256(" ".join(query.casefold().split()).encode()).hexdigest()
    results = cache.get(cache_key)
    if results is None:
        try:
            places = dependencies.get_geocoder().search(query, limit=GEOCODE_LIMIT)
        except ProviderError as exc:
            return _provider_failure(exc)
        except ImproperlyConfigured as exc:
            return _not_configured(exc)
        results = [{"label": p.label, "lat": p.position.lat, "lon": p.position.lon} for p in places]
        cache.set(cache_key, results, GEOCODE_CACHE_SECONDS)
    return Response({"results": results})
