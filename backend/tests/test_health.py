import httpx
import sqlite3
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.db.sqlite import SQLiteRepository
from app.main import create_app
from app.services import ollama as ollama_service


def test_api_health(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "api"}


def test_database_health(client):
    response = client.get("/api/v1/health/db")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "database"}


def test_database_startup_failure_keeps_health_available(monkeypatch, tmp_path):
    get_settings.cache_clear()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'unavailable.db'}")
    monkeypatch.setattr(
        SQLiteRepository,
        "initialize",
        lambda self: (_ for _ in ()).throw(sqlite3.OperationalError("cannot open database")),
    )

    with TestClient(create_app()) as degraded:
        assert degraded.get("/api/v1/health").json() == {"status": "ok", "service": "api"}
        database = degraded.get("/api/v1/health/db")
        assert database.status_code == 200
        assert database.json() == {
            "status": "unavailable",
            "service": "database",
            "message": "The evidence database is unavailable.",
        }
        for path in ("/api/v1/cases", "/api/v1/imports/00000000-0000-4000-8000-000000000000"):
            response = degraded.get(path)
            assert response.status_code == 503
            assert response.json()["code"] == "database_unavailable"
            assert response.json()["retryable"] is True
            assert response.json()["request_id"]
            assert response.headers["x-request-id"] == response.json()["request_id"]
    get_settings.cache_clear()


def test_invalid_database_scheme_still_fails_startup(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/traceveil")
    with pytest.raises(ValueError, match="sqlite"):
        with TestClient(create_app()):
            pass
    get_settings.cache_clear()


def test_ollama_offline_is_degraded_not_failed(client):
    response = client.get("/api/v1/health/ai")
    assert response.status_code == 200
    assert response.json()["available"] is False


def test_ollama_online_reports_installed_model(monkeypatch):
    class MockAsyncClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url):
            request = httpx.Request("GET", url)
            return httpx.Response(
                200,
                request=request,
                json={"models": [{"name": "qwen9b-q4_k_m"}]},
            )

    monkeypatch.setattr(ollama_service.httpx, "AsyncClient", MockAsyncClient)
    settings = Settings(ollama_model="qwen9b-q4_k_m")
    result = __import__("asyncio").run(ollama_service.ollama_status(settings))
    assert result == {
        "available": True,
        "model": "qwen9b-q4_k_m",
        "model_installed": True,
    }
