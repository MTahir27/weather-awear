"""Open-Meteo hourly forecast adapter.

Requests are batched (many coordinates per call) and run concurrently. Units
are requested directly in mph and inches so values compare against the risk
table without conversion.

Every location is fetched for one fixed window (the past hour to 12 days
ahead) and cached for 30 minutes, so any later trip or heatmap touching the
same spot, whatever its departure time, reuses it instead of spending the
free tier's per-minute quota again.
"""

from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from trips.domain.forecast import HourlySeries
from trips.domain.geo import LatLon
from trips.providers.cache import TtlCache
from trips.providers.http import ProviderError, get_json, make_client

PROVIDER = "Open-Meteo"
URL = "https://api.open-meteo.com/v1/forecast"
FORECAST_HORIZON = timedelta(days=16)
BATCH_SIZE = 100
MAX_PARALLEL_REQUESTS = 4
_VARIABLES = ("wind_speed_10m", "wind_gusts_10m", "rain", "showers", "snowfall")
_HOUR_FORMAT = "%Y-%m-%dT%H:%M"
# Departure up to 7 days ahead plus a multi-day trip and a 48 h heatmap fits.
FETCH_WINDOW = timedelta(days=12)
CACHE_TTL_S = 30 * 60
CACHE_MAX_ENTRIES = 5_000

LocationKey = tuple[float, float]


def _key(location: LatLon) -> LocationKey:
    return round(location.lat, 4), round(location.lon, 4)


class OpenMeteoProvider:
    def __init__(
        self,
        client: httpx.Client | None = None,
        cache: TtlCache[LocationKey, HourlySeries] | None = None,
    ) -> None:
        self._client = client or make_client()
        self._cache = cache or TtlCache(ttl_s=CACHE_TTL_S, max_entries=CACHE_MAX_ENTRIES)

    def hourly(
        self, locations: Sequence[LatLon], start: datetime, end: datetime
    ) -> list[HourlySeries]:
        """Hourly forecasts covering [start, end], one per location, in input order.

        Series may extend beyond the requested window. Times past the fetched
        window (or the forecast horizon) simply fall outside the series.
        """
        if not locations:
            return []
        if start.tzinfo is None or end.tzinfo is None:
            raise ValueError("start and end must be timezone-aware.")
        now = datetime.now(UTC)
        window_start = min(_floor_hour(now) - timedelta(hours=1), _floor_hour(start))
        window_end = min(window_start + FETCH_WINDOW, _floor_hour(now + FORECAST_HORIZON))
        if _floor_hour(start) > window_end:
            raise ValueError("The requested window starts beyond the forecast horizon.")
        needed_from = int(_floor_hour(start).timestamp())
        needed_to = int(min(_ceil_hour(end), window_end).timestamp())

        keys = [_key(location) for location in locations]
        found: dict[LocationKey, HourlySeries] = {}
        for key in dict.fromkeys(keys):
            cached = self._cache.get(key)
            if cached is not None and cached.start <= needed_from and cached.end >= needed_to:
                found[key] = cached

        missing = [key for key in dict.fromkeys(keys) if key not in found]
        batches = [missing[i : i + BATCH_SIZE] for i in range(0, len(missing), BATCH_SIZE)]
        if batches:
            with ThreadPoolExecutor(max_workers=MAX_PARALLEL_REQUESTS) as pool:
                fetched = pool.map(
                    lambda batch: self._fetch(
                        [LatLon(*key) for key in batch], window_start, window_end
                    ),
                    batches,
                )
                for batch, series_list in zip(batches, fetched, strict=True):
                    for key, series in zip(batch, series_list, strict=True):
                        self._cache.set(key, series)
                        found[key] = series
        return [found[key] for key in keys]

    def _fetch(self, batch: list[LatLon], first: datetime, last: datetime) -> list[HourlySeries]:
        data = get_json(
            self._client,
            URL,
            {
                "latitude": ",".join(f"{p.lat:.4f}" for p in batch),
                "longitude": ",".join(f"{p.lon:.4f}" for p in batch),
                "hourly": ",".join(_VARIABLES),
                "wind_speed_unit": "mph",
                "precipitation_unit": "inch",
                "timeformat": "unixtime",
                "timezone": "GMT",
                "start_hour": first.strftime(_HOUR_FORMAT),
                "end_hour": last.strftime(_HOUR_FORMAT),
            },
            provider=PROVIDER,
        )
        # A single location is returned as an object, several as a list.
        items = data if isinstance(data, list) else [data]
        if len(items) != len(batch):
            raise ProviderError(PROVIDER, "returned a different number of locations than requested")
        return [_parse_series(item) for item in items]


def _floor_hour(t: datetime) -> datetime:
    return t.astimezone(UTC).replace(minute=0, second=0, microsecond=0)


def _ceil_hour(t: datetime) -> datetime:
    floored = _floor_hour(t)
    return floored if floored == t else floored + timedelta(hours=1)


def _sum_or_none(a: float | None, b: float | None) -> float | None:
    return None if a is None or b is None else a + b


def _parse_series(item: Any) -> HourlySeries:
    try:
        hourly = item["hourly"]
        rain = hourly["rain"]
        showers = hourly["showers"]
        return HourlySeries(
            times=tuple(int(t) for t in hourly["time"]),
            wind_mph=tuple(hourly["wind_speed_10m"]),
            gust_mph=tuple(hourly["wind_gusts_10m"]),
            rain_in=tuple(_sum_or_none(r, s) for r, s in zip(rain, showers, strict=True)),
            snow_in=tuple(hourly["snowfall"]),
        )
    except (KeyError, TypeError, ValueError):
        raise ProviderError(PROVIDER, "forecast has an unexpected shape") from None
