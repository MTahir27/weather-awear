"""Request validation for the trip planning API."""

from datetime import datetime, timedelta
from typing import Any

from django.utils import timezone
from rest_framework import serializers

from trips.domain.geo import LatLon, haversine_m, miles_to_meters
from trips.services.plan_trip import TripRequest

SAMPLE_INTERVALS_MI = (10, 25, 50)
DEFAULT_INTERVAL_MI = 25
MAX_LOAD_LB = 150_000
# Allow for clock skew and time spent filling in the form.
DEPARTURE_PAST_GRACE = timedelta(minutes=15)
# Beyond a week, forecasts for the far end of a long trip are unreliable.
DEPARTURE_MAX_AHEAD = timedelta(days=7)
MIN_TRIP_M = miles_to_meters(1)


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
        now = timezone.now()
        if value < now - DEPARTURE_PAST_GRACE:
            raise serializers.ValidationError("Departure time cannot be in the past.")
        if value > now + DEPARTURE_MAX_AHEAD:
            raise serializers.ValidationError("Departure time must be within the next 7 days.")
        return value

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
        now = timezone.now()
        return TripRequest(
            origin=LatLon(data["origin"]["lat"], data["origin"]["lon"]),
            destination=LatLon(data["destination"]["lat"], data["destination"]["lon"]),
            # A departure within the grace period is treated as "now".
            depart_at=max(data["departure_time"], now),
            load_lb=data["load_weight_lb"],
            interval_mi=int(data["sample_interval_mi"]),
            enforce_hos=data["hours_of_service"],
        )


class GeocodeQuerySerializer(serializers.Serializer[dict[str, str]]):
    q = serializers.CharField(min_length=2, max_length=120, trim_whitespace=True)
