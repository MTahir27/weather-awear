"""Provider-neutral interfaces and data types.

The trip planning service depends only on these protocols, so providers can
be swapped (or faked in tests) without touching business logic.
"""

from dataclasses import dataclass
from typing import Protocol

from trips.domain.geo import LatLon


@dataclass(frozen=True, slots=True)
class Place:
    label: str
    position: LatLon


class Geocoder(Protocol):
    def search(self, query: str, *, limit: int = 5) -> list[Place]: ...
