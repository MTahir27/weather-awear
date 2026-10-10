"""Shared HTTP behaviour for third-party providers.

Transient failures (network errors, timeouts, 429 and 5xx responses) are
retried with exponential backoff. Errors raised from here never include the
request URL, because provider API keys travel in the query string.
"""

from collections.abc import Mapping
from typing import Any

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
USER_AGENT = "weather-awear/1.0 (+https://github.com/MTahir27/weather-awear)"

QueryParams = Mapping[str, str | int | float | bool | list[str]]


class ProviderError(Exception):
    """A third-party API failed or returned an unusable response."""

    def __init__(
        self,
        provider: str,
        message: str,
        *,
        status_code: int | None = None,
        payload: Any = None,
    ) -> None:
        super().__init__(f"{provider}: {message}")
        self.provider = provider
        self.status_code = status_code
        self.payload = payload


class ProviderUnavailable(ProviderError):
    """The provider could not be reached or kept failing after retries."""


def make_client() -> httpx.Client:
    return httpx.Client(timeout=DEFAULT_TIMEOUT, headers={"User-Agent": USER_AGENT})


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status == 429 or status >= 500
    return False


def get_json(
    client: httpx.Client,
    url: str,
    params: QueryParams,
    *,
    provider: str,
    attempts: int = 3,
    backoff_s: float = 0.4,
) -> Any:
    """GET `url` and decode JSON, retrying transient failures."""

    @retry(
        stop=stop_after_attempt(attempts),
        wait=wait_exponential(multiplier=backoff_s, max=4 * backoff_s),
        retry=retry_if_exception(_is_transient),
        reraise=True,
    )
    def send() -> httpx.Response:
        response = client.get(url, params=params)
        response.raise_for_status()
        return response

    try:
        response = send()
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        error_type = ProviderUnavailable if _is_transient(exc) else ProviderError
        raise error_type(
            provider,
            f"request failed with HTTP {status}",
            status_code=status,
            payload=_safe_json(exc.response),
        ) from None
    except httpx.TransportError as exc:
        raise ProviderUnavailable(
            provider, f"could not be reached ({type(exc).__name__})"
        ) from None

    try:
        return response.json()
    except ValueError:
        raise ProviderError(provider, "returned a response that is not valid JSON") from None


def _safe_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return None
