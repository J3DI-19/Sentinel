import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:1")
    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()

