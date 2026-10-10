"""Collect up to three genuinely different truck routes.

Routing providers often return fewer alternatives than requested (TomTom
sometimes returns one or two for Denver to Chicago). Extra candidates are
therefore requested *at the same time* as the main request, so filling the
gap costs no extra latency: routes through via points offset to either side
of the trip's midpoint, and routes avoiding toll roads or motorways. A
candidate is used only when the provider's own alternatives fall short, and
only if it is distinct from the routes already chosen and not an
unreasonable detour.

Trade-off: every plan makes four extra routing calls even when they turn out
not to be needed, in exchange for ~40% lower latency on long trips. Fallbacks
are never waited for when the provider's own alternatives suffice, and when
they are needed only those finishing within FALLBACK_BUDGET_S are used, so
one slow fallback cannot hold up the response.
"""

import logging
import time
from collections.abc import Callable, Sequence
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import datetime

from trips.domain.geo import LatLon, destination_point, haversine_m, initial_bearing_deg
from trips.domain.similarity import is_distinct
from trips.providers.base import Avoid, NoRouteFound, ProviderRoute, RoutingProvider
from trips.providers.http import ProviderError

logger = logging.getLogger(__name__)

TARGET_ROUTE_COUNT = 3
# Alternatives slower than this multiple of the fastest route are not useful options.
MAX_DETOUR_RATIO = 1.5
# Via points sit this fraction of the straight-line distance off the trip's midpoint.
VIA_OFFSET_RATIO = 0.15
VIA_OFFSET_MIN_M = 15_000.0
VIA_OFFSET_MAX_M = 150_000.0
# How long (from the start of the request) fallbacks may take to be considered.
FALLBACK_BUDGET_S = 10.0


@dataclass(frozen=True, slots=True)
class RouteQuery:
    origin: LatLon
    destination: LatLon
    depart_at: datetime
    gross_weight_kg: int


def collect_route_options(router: RoutingProvider, query: RouteQuery) -> list[ProviderRoute]:
    """Up to three distinct routes, best first. Raises NoRouteFound if none exist."""

    def request(
        *, alternatives: int = 0, via: Sequence[LatLon] = (), avoid: Sequence[Avoid] = ()
    ) -> Callable[[], list[ProviderRoute]]:
        return lambda: router.truck_routes(
            query.origin,
            query.destination,
            depart_at=query.depart_at,
            gross_weight_kg=query.gross_weight_kg,
            max_alternatives=alternatives,
            via=via,
            avoid=avoid,
        )

    fallbacks = [request(via=[p]) for p in via_points(query.origin, query.destination)]
    fallbacks += [request(avoid=[Avoid.TOLL_ROADS]), request(avoid=[Avoid.MOTORWAYS])]

    started = time.monotonic()
    # Not a `with` block: leaving one waits for every running request, including
    # fallbacks whose results are no longer needed.
    pool = ThreadPoolExecutor(max_workers=1 + len(fallbacks))
    try:
        main = pool.submit(request(alternatives=TARGET_ROUTE_COUNT - 1))
        fallback_futures = [pool.submit(f) for f in fallbacks]

        routes = _distinct(main.result())  # NoRouteFound / ProviderError propagate
        if len(routes) >= TARGET_ROUTE_COUNT:
            return routes[:TARGET_ROUTE_COUNT]

        remaining = max(0.0, FALLBACK_BUDGET_S - (time.monotonic() - started))
        wait(fallback_futures, timeout=remaining)
        fastest = min(r.travel_time_s for r in routes)
        for candidate in _first_results(fallback_futures):
            if candidate.travel_time_s > fastest * MAX_DETOUR_RATIO:
                continue
            if is_distinct(candidate.points, [r.points for r in routes]):
                routes.append(candidate)
                if len(routes) == TARGET_ROUTE_COUNT:
                    break
        return routes
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def via_points(origin: LatLon, destination: LatLon) -> list[LatLon]:
    """Points to the left and right of the trip's straight-line midpoint."""
    distance = haversine_m(origin, destination)
    heading = initial_bearing_deg(origin, destination)
    midpoint = destination_point(origin, heading, distance / 2)
    offset = min(max(distance * VIA_OFFSET_RATIO, VIA_OFFSET_MIN_M), VIA_OFFSET_MAX_M)
    # Re-measure the heading at the midpoint: great-circle bearings drift en route.
    local_heading = initial_bearing_deg(midpoint, destination)
    return [destination_point(midpoint, local_heading + side, offset) for side in (-90, 90)]


def _distinct(routes: Sequence[ProviderRoute]) -> list[ProviderRoute]:
    kept: list[ProviderRoute] = []
    for route in routes:
        if is_distinct(route.points, [r.points for r in kept]):
            kept.append(route)
    return kept


def _first_results(futures: Sequence[Future[list[ProviderRoute]]]) -> list[ProviderRoute]:
    """Best route of each finished fallback, in preference order; failures are skipped."""
    candidates: list[ProviderRoute] = []
    for future in futures:
        if not future.done():
            continue
        try:
            candidates.extend(future.result()[:1])
        except (NoRouteFound, ProviderError) as exc:
            logger.info("Skipping fallback route candidate: %s", exc)
    return candidates
