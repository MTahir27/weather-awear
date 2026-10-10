import pytest
from django.http import HttpRequest, HttpResponse
from django.test import Client, override_settings
from django.urls import path

from trips.api.errors import server_error


def test_unknown_api_route_returns_json_404(client: Client) -> None:
    response = client.get("/api/does-not-exist")

    assert response.status_code == 404
    assert response["Content-Type"] == "application/json"
    assert response.json() == {"detail": "Not found."}


def _boom(request: HttpRequest) -> HttpResponse:
    raise RuntimeError("unexpected failure")


# This module doubles as a URLconf for the 500 test.
urlpatterns = [path("boom", _boom)]
handler500 = server_error


@override_settings(ROOT_URLCONF=__name__)
def test_unhandled_exception_returns_json_500() -> None:
    client = Client(raise_request_exception=False)

    response = client.get("/boom")

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error."}


@pytest.mark.parametrize("method", ["put", "delete"])
def test_disallowed_method_returns_json_405(client: Client, method: str) -> None:
    response = getattr(client, method)("/api/health")

    assert response.status_code == 405
    assert "detail" in response.json()
