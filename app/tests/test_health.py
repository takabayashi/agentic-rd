from fastapi.testclient import TestClient
from triage import web
from triage.main import app

client = TestClient(app)


def test_healthz_returns_200():
    response = client.get("/healthz")
    assert response.status_code == 200


def test_readyz_200_when_db_ready(monkeypatch):
    monkeypatch.setattr(web, "check_ready", lambda: True)
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_readyz_503_when_db_down(monkeypatch):
    monkeypatch.setattr(web, "check_ready", lambda: False)
    response = client.get("/readyz")
    assert response.status_code == 503


def test_metrics_endpoint_exposes_prometheus_text():
    # Hit a route first so at least one request is recorded.
    client.get("/healthz")
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "triage_http_requests_total" in response.text


def test_root_serves_dashboard_html():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Wikipedia Edit Triage" in response.text
