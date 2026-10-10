"""TomTom Search and Routing API adapters."""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote

import httpx

from trips.domain.geo import LatLon
from trips.providers.base import Avoid, NoRouteFound, Place, ProviderRoute
from trips.providers.http import ProviderError, get_json, make_client

PROVIDER = "TomTom"
BASE_URL = "https://api.tomtom.com"
COUNTRIES = "US,CA"
# TomTom rejects departure times in the past; anything this close is "now".
_DEPART_NOW_WITHIN = timedelta(minutes=1)
_NO_ROUTE_CODES = {"NO_ROUTE_FOUND", "MAP_MATCHING_FAILURE"}


class TomTomRouter:
    def __init__(self, api_key: str, client: httpx.Client | None = None) -> None:
        if not api_key:
            raise ValueError("A TomTom API key is required.")
        self._key = api_key
        self._client = client or make_client()

    def truck_routes(
        self,
        origin: LatLon,
        destination: LatLon,
        *,
        depart_at: datetime,
        gross_weight_kg: int,
        max_alternatives: int = 0,
        via: Sequence[LatLon] = (),
        avoid: Sequence[Avoid] = (),
    ) -> list[ProviderRoute]:
        """Truck routes (best first), timed for traffic at `depart_at`."""
        if depart_at.tzinfo is None:
            raise ValueError("depart_at must be timezone-aware.")
        locations = ":".join(f"{p.lat:.6f},{p.lon:.6f}" for p in (origin, *via, destination))
        params: dict[str, str | int | bool | list[str]] = {
            "key": self._key,
            "travelMode": "truck",
            "vehicleCommercial": True,
            "vehicleWeight": gross_weight_kg,
            "traffic": True,
            "departAt": _depart_param(depart_at),
            "routeRepresentation": "polyline",
            "extendedRouteRepresentation": ["distance", "travelTime"],
            # TomTom does not support alternatives for routes with waypoints.
            "maxAlternatives": 0 if via else max_alternatives,
        }
        if avoid:
            params["avoid"] = [a.value for a in avoid]

        try:
            data = get_json(
                self._client,
                f"{BASE_URL}/routing/1/calculateRoute/{locations}/json",
                params,
                provider=PROVIDER,
            )
        except ProviderError as exc:
            if _error_code(exc.payload) in _NO_ROUTE_CODES:
                raise NoRouteFound("No truck route connects these locations.") from None
            raise

        if not isinstance(data, dict) or not isinstance(data.get("routes"), list):
            raise ProviderError(PROVIDER, "routing response has an unexpected shape")
        if not data["routes"]:
            raise NoRouteFound("No truck route connects these locations.")
        return [_parse_route(route) for route in data["routes"]]


class TomTomGeocoder:
    def __init__(self, api_key: str, client: httpx.Client | None = None) -> None:
        if not api_key:
            raise ValueError("A TomTom API key is required.")
        self._key = api_key
        self._client = client or make_client()

    def search(self, query: str, *, limit: int = 5) -> list[Place]:
        """Places matching a free-text query (addresses, cities, points of interest)."""
        query = query.strip()
        if not query:
            return []
        data = get_json(
            self._client,
            f"{BASE_URL}/search/2/search/{quote(query, safe='')}.json",
            {"key": self._key, "limit": limit, "countrySet": COUNTRIES, "typeahead": True},
            provider=PROVIDER,
        )
        return [_parse_place(result) for result in _results(data)]


def _results(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, dict) or not isinstance(data.get("results"), list):
        raise ProviderError(PROVIDER, "search response has an unexpected shape")
    return [r for r in data["results"] if isinstance(r, dict) and "position" in r]


def _parse_place(result: dict[str, Any]) -> Place:
    try:
        position = LatLon(float(result["position"]["lat"]), float(result["position"]["lon"]))
        address = result.get("address", {}).get("freeformAddress", "")
        name = result.get("poi", {}).get("name")
    except (KeyError, TypeError, ValueError):
        raise ProviderError(PROVIDER, "search result has an unexpected shape") from None
    label = f"{name}, {address}" if name and address else name or address
    return Place(label=label or f"{position.lat:.4f}, {position.lon:.4f}", position=position)


def _depart_param(depart_at: datetime) -> str:
    if depart_at - datetime.now(UTC) <= _DEPART_NOW_WITHIN:
        return "now"
    return depart_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _error_code(payload: Any) -> str | None:
    if isinstance(payload, dict) and isinstance(payload.get("detailedError"), dict):
        code = payload["detailedError"].get("code")
        return code if isinstance(code, str) else None
    return None


def _parse_route(route: Any) -> ProviderRoute:
    try:
        summary = route["summary"]
        length_m = float(summary["lengthInMeters"])
        travel_time_s = float(summary["travelTimeInSeconds"])
        traffic_delay_s = float(summary.get("trafficDelayInSeconds", 0))
        # Legs share their junction point and `progress` indexes this
        # concatenation, so the points are joined as-is.
        points = tuple(
            LatLon(float(p["latitude"]), float(p["longitude"]))
            for leg in route["legs"]
            for p in leg["points"]
        )
        progress = [
            (float(a["distanceInMeters"]), float(a["travelTimeInSeconds"]))
            for a in route.get("progress", [])
        ]
    except (KeyError, TypeError, ValueError):
        raise ProviderError(PROVIDER, "route has an unexpected shape") from None
    if not points:
        raise ProviderError(PROVIDER, "route has no geometry")

    # Guarantee the anchors span the whole route.
    if not progress or progress[0] != (0.0, 0.0):
        progress.insert(0, (0.0, 0.0))
    if progress[-1][0] < length_m:
        progress.append((length_m, travel_time_s))

    return ProviderRoute(
        points=points,
        length_m=length_m,
        travel_time_s=travel_time_s,
        traffic_delay_s=traffic_delay_s,
        progress=tuple(progress),
    )
