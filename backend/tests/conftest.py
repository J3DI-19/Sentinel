import threading

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


def pytest_sessionfinish(session, exitstatus):
    """Turn leaked non-daemon threads into a visible suite failure."""

    leaked = []
    current = threading.current_thread()
    for thread in threading.enumerate():
        if thread is current or thread.daemon or not thread.is_alive():
            continue
        thread.join(timeout=1.0)
        if thread.is_alive():
            leaked.append(thread)
    if not leaked:
        return
    session.exitstatus = pytest.ExitCode.TESTS_FAILED
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    details = ", ".join(f"{thread.name} (id={thread.ident})" for thread in leaked)
    if reporter is not None:
        reporter.write_sep("=", f"leaked non-daemon threads: {details}", red=True)


@pytest.fixture
def client(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("EVIDENCE_STORAGE_PATH", str(tmp_path / "evidence"))
    monkeypatch.setenv("REPORT_STORAGE_PATH", str(tmp_path / "reports"))
    monkeypatch.setenv("LIVE_SOURCE_TOKENS", '{"live-lab-01":"traceveil-demo-token"}')
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:1")
    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()
