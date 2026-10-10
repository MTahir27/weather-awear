"""Open-Meteo hourly forecast adapter.

Requests are batched (many coordinates per call) and run concurrently. Units
are requested directly in mph and inches so values compare against the risk
table without conversion.
"""

from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from trips.domain.forecast import HourlySeries
from trips.domain.geo import LatLon
from trips.providers.http import ProviderError, get_json, make_client

PROVIDER = "Open-Meteo"
URL = "https://api.open-meteo.com/v1/forecast"
FORECAST_HORIZON = timedelta(days=16)
BATCH_SIZE = 100
MAX_PARALLEL_REQUESTS = 4
_VARIABLES = ("wind_speed_10m", "wind_gusts_10m", "rain", "showers", "snowfall")
_HOUR_FORMAT = "%Y-%m-%dT%H:%M"


class OpenMeteoProvider:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or make_client()

    def hourly(
        self, locations: Sequence[LatLon], start: datetime, end: datetime
    ) -> list[HourlySeries]:
        """Hourly forecasts covering [start, end], one per location, in input order.

        The window is widened to whole hours and capped at the forecast
        horizon; later times simply fall outside the returned series.
        """
        if not locations:
            return []
        if start.tzinfo is None or end.tzinfo is None:
            raise ValueError("start and end must be timezone-aware.")
        first_hour = _floor_hour(start)
        last_hour = min(_ceil_hour(end), _floor_hour(datetime.now(UTC) + FORECAST_HORIZON))
        if last_hour < first_hour:
            raise ValueError("The requested window starts beyond the forecast horizon.")

        batches = [
            list(locations[i : i + BATCH_SIZE]) for i in range(0, len(locations), BATCH_SIZE)
        ]
        with ThreadPoolExecutor(max_workers=MAX_PARALLEL_REQUESTS) as pool:
            results = pool.map(lambda batch: self._fetch(batch, first_hour, last_hour), batches)
            return [series for batch_result in results for series in batch_result]

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
