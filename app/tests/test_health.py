from fastapi.testclient import TestClient
from triage.main import app

client = TestClient(app)


def test_healthz_returns_200():
    response = client.get("/healthz")
    assert response.status_code == 200


def test_root_serves_dashboard_html():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Wikipedia Edit Triage" in response.text
