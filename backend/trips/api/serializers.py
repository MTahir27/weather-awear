"""Request validation for the trip planning API."""

from datetime import datetime, timedelta
from typing import Any

from django.utils import timezone
from rest_framework import serializers

from trips.domain.geo import LatLon, haversine_m, miles_to_meters
from trips.domain.polyline import decode
from trips.services.heatmap import HeatmapRequest
from trips.services.plan_trip import TripRequest

SAMPLE_INTERVALS_MI = (10, 25, 50)
DEFAULT_INTERVAL_MI = 25
MAX_LOAD_LB = 150_000
# Allow for clock skew and time spent filling in the form.
DEPARTURE_PAST_GRACE = timedelta(minutes=15)
# Beyond a week, forecasts for the far end of a long trip are unreliable.
DEPARTURE_MAX_AHEAD = timedelta(days=7)
MIN_TRIP_M = miles_to_meters(1)
MAX_HEATMAP_ROUTES = 3
# Generous for simplified route geometry (~1,000 points per 1,000 miles).
MAX_GEOMETRY_CHARS = 50_000


def validate_departure(value: datetime) -> datetime:
    now = timezone.now()
    if value < now - DEPARTURE_PAST_GRACE:
        raise serializers.ValidationError("Departure time cannot be in the past.")
    if value > now + DEPARTURE_MAX_AHEAD:
        raise serializers.ValidationError("Departure time must be within the next 7 days.")
    return value


def effective_departure(value: datetime) -> datetime:
    """A departure within the grace period is treated as "now"."""
    return max(value, timezone.now())


class PointSerializer(serializers.Serializer[LatLon]):
    """A coordinate. Extra keys (such as a display label) are ignored."""

    lat = serializers.FloatField(min_value=-90, max_value=90)
    lon = serializers.FloatField(min_value=-180, max_value=180)


class TripRequestSerializer(serializers.Serializer[TripRequest]):
    origin = PointSerializer()
    destination = PointSerializer()
    departure_time = serializers.DateTimeField()
    load_weight_lb = serializers.FloatField(min_value=0, max_value=MAX_LOAD_LB)
    sample_interval_mi = serializers.ChoiceField(
        choices=SAMPLE_INTERVALS_MI, default=DEFAULT_INTERVAL_MI
    )
    hours_of_service = serializers.BooleanField(default=True)

    def validate_departure_time(self, value: datetime) -> datetime:
        return validate_departure(value)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        origin = LatLon(attrs["origin"]["lat"], attrs["origin"]["lon"])
        destination = LatLon(attrs["destination"]["lat"], attrs["destination"]["lon"])
        if haversine_m(origin, destination) < MIN_TRIP_M:
            raise serializers.ValidationError(
                {"destination": "Destination must be at least 1 mile from the origin."}
            )
        return attrs

    def to_trip_request(self) -> TripRequest:
        data = self.validated_data
        return TripRequest(
            origin=LatLon(data["origin"]["lat"], data["origin"]["lon"]),
            destination=LatLon(data["destination"]["lat"], data["destination"]["lon"]),
            depart_at=effective_departure(data["departure_time"]),
            load_lb=data["load_weight_lb"],
            interval_mi=int(data["sample_interval_mi"]),
            enforce_hos=data["hours_of_service"],
        )


class GeocodeQuerySerializer(serializers.Serializer[dict[str, str]]):
    q = serializers.CharField(min_length=2, max_length=120, trim_whitespace=True)


class HeatmapRequestSerializer(serializers.Serializer[HeatmapRequest]):
    routes = serializers.ListField(
        child=serializers.CharField(max_length=MAX_GEOMETRY_CHARS, trim_whitespace=False),
        min_length=1,
        max_length=MAX_HEATMAP_ROUTES,
    )
    departure_time = serializers.DateTimeField()
    load_weight_lb = serializers.FloatField(min_value=0, max_value=MAX_LOAD_LB)

    def validate_departure_time(self, value: datetime) -> datetime:
        return validate_departure(value)

    def validate_routes(self, value: list[str]) -> list[list[LatLon]]:
        try:
            routes = [decode(encoded) for encoded in value]
        except ValueError:
            raise serializers.ValidationError("Route geometry is not a valid polyline.") from None
        if any(len(route) < 2 for route in routes):
            raise serializers.ValidationError("Each route needs at least two points.")
        return routes

    def to_heatmap_request(self) -> HeatmapRequest:
        data = self.validated_data
        return HeatmapRequest(
            routes=data["routes"],
            depart_at=effective_departure(data["departure_time"]),
            load_lb=data["load_weight_lb"],
        )
