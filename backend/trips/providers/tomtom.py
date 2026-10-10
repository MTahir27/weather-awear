"""TomTom Search and Routing API adapters."""

from typing import Any
from urllib.parse import quote

import httpx

from trips.domain.geo import LatLon
from trips.providers.base import Place
from trips.providers.http import ProviderError, get_json, make_client

PROVIDER = "TomTom"
BASE_URL = "https://api.tomtom.com"
COUNTRIES = "US,CA"


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
