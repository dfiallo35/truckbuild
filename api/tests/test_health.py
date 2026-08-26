from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_healthz_reports_ok() -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
