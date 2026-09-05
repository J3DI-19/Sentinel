"""Step 5 bridge forwarding tests.

Runs hardware/mqtt_bridge/bridge.py against the real FastAPI app (via
TestClient) with no MQTT broker and no physical device. Covers the
PR #8 review-driven behaviors:

* on_message enqueues to the durable spool; the worker drains it.
* TV5-03: topic source_id vs payload source_id mismatch is refused.
* TV5-07: transient backend failures retry; terminal failures dead-letter.
* TV5-09: after a successful backend forward, the bridge publishes an
  ACK on tv/dev/<source>/ack.
* TV5-02: configure_tls refuses to run without CA/cert/key files.
* Backend JSON token format parses; malformed formats are rejected.
* LWT status messages become heartbeat frames.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
BRIDGE_PATH = REPO_ROOT / "hardware" / "mqtt_bridge" / "bridge.py"


def _load_bridge_module():
    spec = importlib.util.spec_from_file_location("traceveil_bridge", BRIDGE_PATH)
    if spec is None or spec.loader is None:  # pragma: no cover
        pytest.skip(f"bridge module not present at {BRIDGE_PATH}")
    module = importlib.util.module_from_spec(spec)

    # The bridge tries to import paho at module import time. Stub it so the
    # test does not require paho in the backend virtualenv.
    if "paho.mqtt.client" not in sys.modules:
        stub_client = SimpleNamespace(
            Client=lambda **_kwargs: SimpleNamespace(),
            MQTTMessage=SimpleNamespace,
        )
        sys.modules["paho"] = SimpleNamespace(mqtt=SimpleNamespace(client=stub_client))
        sys.modules["paho.mqtt"] = sys.modules["paho"].mqtt
        sys.modules["paho.mqtt.client"] = stub_client

    spec.loader.exec_module(module)
    return module


bridge_module = _load_bridge_module()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _wait_for_device(client, case_id: int, source_id: str, timeout_s: float = 3.0):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        devices = client.get(f"/api/v1/cases/{case_id}/live/devices").json()
        if any(item.get("source_id") == source_id for item in devices.get("items", [])):
            return devices
        time.sleep(0.01)
    raise AssertionError(f"device {source_id!r} did not appear within {timeout_s}s")


def _make_message(topic: str, payload) -> SimpleNamespace:
    body = payload if isinstance(payload, (bytes, str)) else json.dumps(payload)
    if isinstance(body, str):
        body = body.encode("utf-8")
    return SimpleNamespace(topic=topic, payload=body)


def _new_case_and_session(client, source_id: str = "live-lab-01") -> int:
    case = client.post(
        "/api/v1/cases",
        json={"name": "Step 5 bridge", "description": "bridge test", "owner": "test"},
    ).json()
    case_id = int(case["id"])
    client.post(
        f"/api/v1/cases/{case_id}/live-sessions",
        json={"label": "bridge", "source_ids": [source_id], "stale_after_seconds": 30},
    )
    return case_id


class FakeMqttClient:
    """Records publish() calls so ACK behavior can be asserted."""

    def __init__(self) -> None:
        self.published: list[tuple[str, str, int, bool]] = []

    def publish(self, topic: str, payload: str, qos: int = 0, retain: bool = False) -> None:
        self.published.append((topic, payload, qos, retain))


class _FakeResponse:
    def __init__(self, response):
        self.status = response.status_code
        self._body = response.content

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


@pytest.fixture
def bridge_client_urlopen(client, monkeypatch):
    """Redirects the bridge module's urlopen to the FastAPI TestClient."""

    def fake_urlopen(req, timeout=None):  # noqa: ARG001
        response = client.post(
            "/api/v1/live/telemetry",
            content=req.data,
            headers={k: v for k, v in req.header_items()},
        )
        if response.status_code >= 400:
            from urllib.error import HTTPError
            raise HTTPError(
                url=req.full_url,
                code=response.status_code,
                msg=response.reason_phrase,
                hdrs=response.headers,
                fp=None,
            )
        return _FakeResponse(response)

    monkeypatch.setattr(bridge_module.urlrequest, "urlopen", fake_urlopen)


def _build_bridge(tmp_path, case_id, *, mqtt_client=None):
    spool = bridge_module.Spool(tmp_path / "spool.sqlite")
    return bridge_module.Bridge(
        api_base="http://testserver/api/v1",
        tokens={"live-lab-01": "traceveil-demo-token"},
        case_id_default=case_id,
        spool=spool,
        mqtt_client=mqtt_client,
    ), spool


def _drain(bridge, max_iterations=20):
    for _ in range(max_iterations):
        if not bridge.process_once():
            return
    raise AssertionError("bridge spool did not drain within iteration budget")


# ---------------------------------------------------------------------------
# Happy path: MQTT frame -> spool -> backend -> ACK
# ---------------------------------------------------------------------------
def test_bridge_forwards_esp32_frame_and_produces_receipt(client, bridge_client_urlopen, tmp_path):
    case_id = _new_case_and_session(client)
    fake_mqtt = FakeMqttClient()
    bridge, _spool = _build_bridge(tmp_path, case_id, mqtt_client=fake_mqtt)

    msg = _make_message(
        "tv/dev/live-lab-01/telemetry",
        {
            "schema_version": "1.0", "case_id": case_id,
            "source_id": "live-lab-01", "device_id": "esp32-lab-01",
            "event_type": "telemetry",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "sequence": 1,
            "metrics": {"temperature_c": 24.5, "humidity_pct": 41.0, "motion": False},
        },
    )
    bridge.on_message(None, None, msg)
    _drain(bridge)

    devices = _wait_for_device(client, case_id, "live-lab-01")
    assert devices["total"] >= 1

    # TV5-09: after backend accepts the frame, an ACK is published.
    ack_publishes = [p for p in fake_mqtt.published if p[0].endswith("/ack")]
    assert len(ack_publishes) == 1
    topic, payload, qos, _retain = ack_publishes[0]
    assert topic == "tv/dev/live-lab-01/ack"
    assert json.loads(payload) == {"sequence": 1}
    assert qos == 1


def test_bridge_translates_lwt_status_into_heartbeat(client, bridge_client_urlopen, tmp_path):
    case_id = _new_case_and_session(client)
    bridge, _spool = _build_bridge(tmp_path, case_id)
    bridge.on_message(None, None, _make_message("tv/dev/live-lab-01/status", {"status": "offline"}))
    _drain(bridge)

    devices = _wait_for_device(client, case_id, "live-lab-01")
    assert devices["total"] >= 1


# ---------------------------------------------------------------------------
# TV5-03: topic vs payload mismatch
# ---------------------------------------------------------------------------
def test_bridge_refuses_topic_and_payload_source_mismatch(client, bridge_client_urlopen, tmp_path, caplog):
    case_id = _new_case_and_session(client, source_id="live-lab-01")
    bridge, spool = _build_bridge(tmp_path, case_id)

    msg = _make_message(
        "tv/dev/live-lab-01/telemetry",   # topic says lab-01
        {
            "schema_version": "1.0", "case_id": case_id,
            "source_id": "live-lab-02", "device_id": "d",   # payload says lab-02 (spoof)
            "event_type": "telemetry",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "sequence": 1, "metrics": {"temperature_c": 20.0},
        },
    )
    with caplog.at_level("ERROR", logger="traceveil.bridge"):
        bridge.on_message(None, None, msg)

    assert any("topic/source mismatch" in r.message for r in caplog.records)
    assert spool.depth() == (0, 0)  # nothing spooled, nothing dead-lettered


# ---------------------------------------------------------------------------
# Unregistered sources
# ---------------------------------------------------------------------------
def test_bridge_drops_frames_from_unregistered_source(client, bridge_client_urlopen, tmp_path, caplog):
    case_id = _new_case_and_session(client)
    bridge, spool = _build_bridge(tmp_path, case_id)

    msg = _make_message(
        "tv/dev/rogue-node-01/telemetry",
        {
            "schema_version": "1.0", "case_id": case_id,
            "source_id": "rogue-node-01", "device_id": "rogue-node-01",
            "event_type": "telemetry",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "sequence": 1, "metrics": {"temperature_c": 20.0},
        },
    )
    with caplog.at_level("WARNING", logger="traceveil.bridge"):
        bridge.on_message(None, None, msg)

    assert any("unregistered" in r.message for r in caplog.records)
    assert spool.depth() == (0, 0)


# ---------------------------------------------------------------------------
# TV5-07: transient failures retry, terminal failures dead-letter
# ---------------------------------------------------------------------------
def test_transient_failure_defers_frame(tmp_path, monkeypatch, caplog):
    """5xx from the backend causes a retry with backoff, not a drop."""
    spool = bridge_module.Spool(tmp_path / "spool.sqlite", max_attempts=3)
    bridge = bridge_module.Bridge(
        api_base="http://testserver/api/v1",
        tokens={"live-lab-01": "t"},
        case_id_default=1,
        spool=spool,
    )
    calls = {"n": 0}

    def flaky_post(source_id, body):
        calls["n"] += 1
        return (503, "unavailable")
    monkeypatch.setattr(bridge, "_post", flaky_post)

    row_id = spool.enqueue("live-lab-01", {"sequence": 1})
    assert row_id is not None

    with caplog.at_level("WARNING", logger="traceveil.bridge"):
        bridge.process_once()
    assert calls["n"] == 1
    assert spool.depth() == (1, 0)         # still queued
    assert spool.attempts(row_id) == 1     # attempt counter advanced

    # After max_attempts, the row moves to dead_letter.
    spool.defer(row_id, 0)
    bridge.process_once()
    spool.defer(row_id, 0)
    bridge.process_once()
    assert spool.depth() == (0, 1)


def test_terminal_failure_dead_letters_immediately(tmp_path, monkeypatch):
    spool = bridge_module.Spool(tmp_path / "spool.sqlite")
    bridge = bridge_module.Bridge(
        api_base="http://testserver/api/v1",
        tokens={"live-lab-01": "t"},
        case_id_default=1,
        spool=spool,
    )
    monkeypatch.setattr(bridge, "_post", lambda s, b: (422, "malformed"))
    spool.enqueue("live-lab-01", {"sequence": 1})
    bridge.process_once()
    assert spool.depth() == (0, 1)


def test_spool_survives_backend_outage_then_recovers(
    client, bridge_client_urlopen, tmp_path, monkeypatch
):
    case_id = _new_case_and_session(client)
    fake_mqtt = FakeMqttClient()
    bridge, spool = _build_bridge(tmp_path, case_id, mqtt_client=fake_mqtt)

    from urllib.error import URLError
    def down(_req, timeout=None):
        raise URLError("connection refused")
    monkeypatch.setattr(bridge_module.urlrequest, "urlopen", down)

    msg = _make_message(
        "tv/dev/live-lab-01/telemetry",
        {
            "schema_version": "1.0", "case_id": case_id,
            "source_id": "live-lab-01", "device_id": "d",
            "event_type": "telemetry",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "sequence": 42, "metrics": {"temperature_c": 20.0},
        },
    )
    bridge.on_message(None, None, msg)
    bridge.process_once()
    assert spool.depth() == (1, 0)  # still spooled

    # Backend comes back; restore the real forwarder and drain immediately.
    def fake_urlopen(req, timeout=None):
        response = client.post(
            "/api/v1/live/telemetry",
            content=req.data,
            headers={k: v for k, v in req.header_items()},
        )
        if response.status_code >= 400:
            from urllib.error import HTTPError
            raise HTTPError(req.full_url, response.status_code, response.reason_phrase,
                            response.headers, None)
        return _FakeResponse(response)
    monkeypatch.setattr(bridge_module.urlrequest, "urlopen", fake_urlopen)
    spool.defer(1, 0)               # skip the exponential backoff for the test
    bridge.process_once()

    assert spool.depth() == (0, 0)
    _wait_for_device(client, case_id, "live-lab-01")
    assert any(p[0].endswith("/ack") for p in fake_mqtt.published)


# ---------------------------------------------------------------------------
# TV5-02: TLS material must be present
# ---------------------------------------------------------------------------
def test_configure_tls_requires_all_material(tmp_path):
    class DummyClient:
        def __init__(self): self.set = None
        def tls_set(self, **kw): self.set = kw

    ca = tmp_path / "ca.pem"; ca.write_text("ca")
    cert = tmp_path / "cert.pem"; cert.write_text("cert")
    key = tmp_path / "key.pem"; key.write_text("key")

    ok = DummyClient()
    bridge_module.configure_tls(ok, str(ca), str(cert), str(key))
    assert ok.set is not None

    with pytest.raises(SystemExit):
        bridge_module.configure_tls(DummyClient(), "", str(cert), str(key))
    with pytest.raises(SystemExit):
        bridge_module.configure_tls(DummyClient(), str(ca), "", str(key))
    with pytest.raises(SystemExit):
        bridge_module.configure_tls(DummyClient(), str(ca), str(cert), "")
    with pytest.raises(SystemExit):
        bridge_module.configure_tls(DummyClient(), str(ca), str(cert), str(tmp_path / "missing"))


# ---------------------------------------------------------------------------
# Config parsing
# ---------------------------------------------------------------------------
def test_load_source_tokens_reads_backend_json_format():
    tokens = bridge_module.load_source_tokens('{"esp32-lab-01": "abc123"}')
    assert tokens == {"esp32-lab-01": "abc123"}

    with pytest.raises(SystemExit):
        bridge_module.load_source_tokens("")
    with pytest.raises(SystemExit):
        bridge_module.load_source_tokens("not-json")
    with pytest.raises(SystemExit):
        bridge_module.load_source_tokens("{}")


def test_parse_source_from_topic():
    assert bridge_module.parse_source_from_topic("tv/dev/esp32-lab-01/telemetry") == "esp32-lab-01"
    assert bridge_module.parse_source_from_topic("tv/dev/esp32-lab-01/status") == "esp32-lab-01"
    assert bridge_module.parse_source_from_topic("other/topic") is None
    assert bridge_module.parse_source_from_topic("tv/dev/x/y/z") is None
