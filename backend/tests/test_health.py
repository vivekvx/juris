"""Tests for the /health endpoint."""
from fastapi.testclient import TestClient


def test_health_returns_200(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200


def test_health_body(client: TestClient) -> None:
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["service"] == "juris-backend"


def test_health_content_type(client: TestClient) -> None:
    resp = client.get("/health")
    assert "application/json" in resp.headers["content-type"]


def test_health_requires_no_firebase(client: TestClient) -> None:
    """Health endpoint must work without Firebase credentials set."""
    # client fixture creates app without Firebase — if this passes, health is dependency-free.
    resp = client.get("/health")
    assert resp.status_code == 200
