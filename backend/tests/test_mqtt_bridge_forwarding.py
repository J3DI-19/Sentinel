"""Step 5 bridge forwarding tests.

Runs the hardware/mqtt_bridge/bridge.py forwarding logic against the real
FastAPI app (via TestClient) with no MQTT broker and no physical device.
Confirms that a frame published by an ESP32 node on
``tv/dev/<source_id>/telemetry`` reaches ``/api/v1/live/telemetry`` with the
correct token, becomes a durable receipt and canonical event, and that LWT
``status`` messages are translated into ``heartbeat`` events.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from urllib import request as urlrequest

import pytest
from time import sleep


REPO_ROOT = Path(__file__).resolve().parents[2]


def _wait_for_device(client, case_id: int, source_id: str, timeout_s: float = 3.0):
    """Live ingestion is queued; the background worker completes it shortly
    after the POST returns 202. Poll like the existing phase 3 tests do."""
    deadline_iters = int(timeout_s / 0.01)
    for _ in range(deadline_iters):
        devices = client.get(f"/api/v1/cases/{case_id}/live/devices").json()
        if any(item.get("source_id") == source_id for item in devices.get("items", [])):
            return devices
        sleep(0.01)
    raise AssertionError(f"device {source_id!r} did not appear within {timeout_s}s")
BRIDGE_PATH = REPO_ROOT / "hardware" / "mqtt_bridge" / "bridge.py"


def _load_bridge_module():
    spec = importlib.util.spec_from_file_location("traceveil_bridge", BRIDGE_PATH)
    if spec is None or spec.loader is None:  # pragma: no cover
        pytest.skip(f"bridge module not present at {BRIDGE_PATH}")
    module = importlib.util.module_from_spec(spec)

    # Bridge imports paho.mqtt.client at module import time. Provide a minimal
    # stub so the test does not depend on paho being installed in the backend
    # virtualenv (the bridge has its own requirements.txt for deployment).
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


@pytest.fixture
def bridge_client_urlopen(client, monkeypatch):
    """Redirects urllib.request.urlopen inside the bridge module to the
    TestClient. Every POST the bridge makes therefore hits the real FastAPI
    app in-process."""

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


def _make_message(topic: str, payload: dict | str) -> SimpleNamespace:
    body = payload if isinstance(payload, (bytes, str)) else json.dumps(payload)
    if isinstance(body, str):
        body = body.encode("utf-8")
    return SimpleNamespace(topic=topic, payload=body)


def _new_case_and_session(client, source_id: str = "live-lab-01") -> int:
    case = client.post(
        "/api/v1/cases",
        json={"name": "Step 5 bridge", "description": "bridge forwarding test", "owner": "test"},
    ).json()
    case_id = int(case["id"])
    client.post(
        f"/api/v1/cases/{case_id}/live-sessions",
        json={"label": "bridge", "source_ids": [source_id], "stale_after_seconds": 30},
    )
    return case_id


def test_bridge_forwards_esp32_frame_and_produces_receipt(client, bridge_client_urlopen):
    case_id = _new_case_and_session(client)
    bridge = bridge_module.Bridge(
        api_base="http://testserver/api/v1",
        tokens={"live-lab-01": "traceveil-demo-token"},
        case_id_default=case_id,
    )
    msg = _make_message(
        "tv/dev/live-lab-01/telemetry",
        {
            "schema_version": "1.0",
            "case_id": case_id,
            "source_id": "live-lab-01",
            "device_id": "esp32-lab-01",
            "event_type": "telemetry",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "sequence": 1,
            "metrics": {"temperature_c": 24.5, "humidity_pct": 41.0, "motion": False},
        },
    )
    bridge.on_message(None, None, msg)
    devices = _wait_for_device(client, case_id, "live-lab-01")
    assert devices["total"] >= 1


def test_bridge_translates_lwt_status_into_heartbeat(client, bridge_client_urlopen):
    case_id = _new_case_and_session(client)
    bridge = bridge_module.Bridge(
        api_base="http://testserver/api/v1",
        tokens={"live-lab-01": "traceveil-demo-token"},
        case_id_default=case_id,
    )
    msg = _make_message("tv/dev/live-lab-01/status", {"status": "offline"})
    bridge.on_message(None, None, msg)

    devices = _wait_for_device(client, case_id, "live-lab-01")
    assert devices["total"] >= 1
    metrics = client.get(f"/api/v1/cases/{case_id}/live/metrics").json()
    assert metrics["case_id"] == case_id


def test_bridge_drops_frames_from_unregistered_source(client, bridge_client_urlopen, caplog):
    case_id = _new_case_and_session(client)
    bridge = bridge_module.Bridge(
        api_base="http://testserver/api/v1",
        tokens={"live-lab-01": "traceveil-demo-token"},
        case_id_default=case_id,
    )
    msg = _make_message(
        "tv/dev/rogue-node-01/telemetry",
        {
            "schema_version": "1.0",
            "case_id": case_id,
            "source_id": "rogue-node-01",
            "device_id": "rogue-node-01",
            "event_type": "telemetry",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "sequence": 1,
            "metrics": {"temperature_c": 20.0},
        },
    )
    with caplog.at_level("WARNING", logger="traceveil.bridge"):
        bridge.on_message(None, None, msg)

    assert any("unregistered" in record.message for record in caplog.records)
    devices = client.get(f"/api/v1/cases/{case_id}/live/devices").json()
    assert not any(item["source_id"] == "rogue-node-01" for item in devices["items"])


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
