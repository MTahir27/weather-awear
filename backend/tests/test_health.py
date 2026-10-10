from django.test import Client


def test_health_returns_ok(client: Client) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_rejects_post(client: Client) -> None:
    response = client.post("/api/health")

    assert response.status_code == 405


def test_http_client_loggers_cannot_leak_api_keys() -> None:
    # httpx logs request URLs (which carry API keys) at INFO.
    import logging

    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING
    assert logging.getLogger("httpcore").getEffectiveLevel() >= logging.WARNING
