import pytest

from api import views

pytestmark = pytest.mark.django_db

HEALTH_URL = "/api/health/"


def test_health_returns_ok_envelope(client):
    response = client.get(HEALTH_URL)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["data"]["service"] == "rangdrishti-api"
    assert body["data"]["database"] == "ok"
    assert {"version", "time"} <= body["data"].keys()


def test_health_reports_503_when_database_unavailable(client, monkeypatch):
    monkeypatch.setattr(views, "database_is_available", lambda: False)

    response = client.get(HEALTH_URL)

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "error"
    assert body["error"]["code"] == "service_unavailable"
    assert body["error"]["details"]["database"] == "unavailable"


def test_health_rejects_post_with_envelope(client):
    response = client.post(HEALTH_URL)

    assert response.status_code == 405
    assert response.json()["error"]["code"] == "method_not_allowed"


def test_unknown_api_route_returns_json_404(client):
    response = client.get("/api/does-not-exist/")

    assert response.status_code == 404
    assert response["Content-Type"].startswith("application/json")
    assert response.json()["error"]["code"] == "not_found"


def test_cors_allows_configured_origin(client, settings):
    settings.CORS_ALLOWED_ORIGINS = ["http://localhost:5173"]

    response = client.get(HEALTH_URL, HTTP_ORIGIN="http://localhost:5173")

    assert response["Access-Control-Allow-Origin"] == "http://localhost:5173"


def test_cors_blocks_unknown_origin(client, settings):
    settings.CORS_ALLOWED_ORIGINS = ["http://localhost:5173"]

    response = client.get(HEALTH_URL, HTTP_ORIGIN="https://evil.example")

    assert "Access-Control-Allow-Origin" not in response
