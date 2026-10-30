from __future__ import annotations

from src.api.routes import health


async def _database_ok() -> None:
    return None


async def _database_down() -> None:
    raise RuntimeError("connection refused")


def test_health_ok(client, monkeypatch):
    monkeypatch.setattr(health, "check_db", _database_down)

    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["database"] == "not_checked"
    assert payload["environment"] == "test"


def test_api_health_ok(client, monkeypatch):
    monkeypatch.setattr(health, "check_db", _database_down)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_ready_ok(client, monkeypatch):
    monkeypatch.setattr(health, "check_db", _database_ok)

    response = client.get("/health/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["database"] == "connected"


def test_api_health_ready_ok(client, monkeypatch):
    monkeypatch.setattr(health, "check_db", _database_ok)

    response = client.get("/api/health/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_ready_database_down(client, monkeypatch):
    monkeypatch.setattr(health, "check_db", _database_down)

    response = client.get("/health/ready")

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "error"
    assert payload["database"] == "disconnected"
    assert "connection refused" in payload["error"]
