from collections.abc import Iterator

import httpx
import pytest
import respx

from trips.providers.http import ProviderError, ProviderUnavailable, get_json, make_client

URL = "https://api.example.com/data"
SECRET = "super-secret-key"  # noqa: S105 - fake key used to assert it never leaks


@pytest.fixture
def client() -> Iterator[httpx.Client]:
    with make_client() as c:
        yield c


def fetch(client: httpx.Client) -> object:
    return get_json(client, URL, {"key": SECRET}, provider="Example", backoff_s=0)


@respx.mock
def test_returns_decoded_json(client: httpx.Client) -> None:
    route = respx.get(URL).respond(json={"ok": True})

    assert fetch(client) == {"ok": True}
    assert route.calls.last.request.url.params["key"] == SECRET


@respx.mock
def test_sends_identifying_user_agent(client: httpx.Client) -> None:
    route = respx.get(URL).respond(json={})

    fetch(client)

    assert route.calls.last.request.headers["User-Agent"].startswith("weather-awear/")


@respx.mock
@pytest.mark.parametrize("status", [429, 500, 503])
def test_retries_transient_status_then_succeeds(client: httpx.Client, status: int) -> None:
    route = respx.get(URL).mock(
        side_effect=[httpx.Response(status), httpx.Response(200, json={"ok": True})]
    )

    assert fetch(client) == {"ok": True}
    assert route.call_count == 2


@respx.mock
def test_retries_network_errors_then_reports_unavailable(client: httpx.Client) -> None:
    route = respx.get(URL).mock(side_effect=httpx.ConnectTimeout("timed out"))

    with pytest.raises(ProviderUnavailable, match="could not be reached") as excinfo:
        fetch(client)

    assert route.call_count == 3
    assert SECRET not in str(excinfo.value)


@respx.mock
def test_persistent_server_error_is_unavailable(client: httpx.Client) -> None:
    respx.get(URL).respond(502)

    with pytest.raises(ProviderUnavailable) as excinfo:
        fetch(client)

    assert excinfo.value.status_code == 502


@respx.mock
def test_client_error_is_not_retried_and_keeps_payload(client: httpx.Client) -> None:
    route = respx.get(URL).respond(400, json={"detailedError": {"code": "NO_ROUTE_FOUND"}})

    with pytest.raises(ProviderError) as excinfo:
        fetch(client)

    assert route.call_count == 1
    assert not isinstance(excinfo.value, ProviderUnavailable)
    assert excinfo.value.status_code == 400
    assert excinfo.value.payload == {"detailedError": {"code": "NO_ROUTE_FOUND"}}
    assert SECRET not in str(excinfo.value)
    assert str(excinfo.value) == "Example: request failed with HTTP 400"


@respx.mock
def test_error_payload_may_be_non_json(client: httpx.Client) -> None:
    respx.get(URL).respond(403, text="Forbidden")

    with pytest.raises(ProviderError) as excinfo:
        fetch(client)

    assert excinfo.value.payload is None


@respx.mock
def test_invalid_json_body_is_a_provider_error(client: httpx.Client) -> None:
    respx.get(URL).respond(200, text="<html>oops</html>")

    with pytest.raises(ProviderError, match="not valid JSON"):
        fetch(client)


def test_unrelated_exceptions_are_not_retried() -> None:
    from trips.providers.http import _is_transient

    assert not _is_transient(ValueError("bug"))
