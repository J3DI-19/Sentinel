import httpx

from app.core.config import Settings
from app.services import ollama as ollama_service


def test_api_health(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "api"}


def test_database_health(client):
    response = client.get("/api/v1/health/db")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "database"}


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
