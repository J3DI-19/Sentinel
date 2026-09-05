"""Backend tests for the two PR #9 re-review "deferred" items:

* TV5-11: replay of a previously accepted (source_id, sequence) frame
  emits a `live.replay_detected` audit row while the receipt itself
  still returns `duplicate=true` unchanged.

* TV5-12: live-endpoint authentication failures produce a bounded,
  structured `live.auth_failure` audit row that never stores the
  presented token or unbounded attacker payload, and are rate-limited
  per (source_id or client IP) to a fixed number per minute.
"""
from __future__ import annotations

from time import sleep


VALID_TOKEN = "traceveil-demo-token"


def _make_case(client) -> int:
    return client.post("/api/v1/cases", json={"name": "TV5-11/12 audit"}).json()["id"]


def _make_session(client, case_id: int, source_ids: list[str]) -> str:
    return client.post(
        f"/api/v1/cases/{case_id}/live-sessions",
        json={"label": "audit", "source_ids": source_ids},
    ).json()["session_id"]


def _wait_receipt(client, receipt_id: str) -> dict:
    for _ in range(300):
        current = client.get(f"/api/v1/live/receipts/{receipt_id}").json()
        if current["status"] in {"completed", "failed", "rejected"}:
            return current
        sleep(0.01)
    raise AssertionError("live receipt did not complete")


def _audit_actions(client, case_id: int) -> list[dict]:
    return client.get(f"/api/v1/cases/{case_id}/audit").json()["items"]


# ---------------------------------------------------------------------------
# TV5-11 - replay detected audit signal
# ---------------------------------------------------------------------------
def test_replay_of_accepted_sequence_emits_replay_detected_audit(client):
    cid = _make_case(client)
    _make_session(client, cid, ["live-lab-01"])
    payload = {
        "schema_version": "1.0", "case_id": cid, "source_id": "live-lab-01",
        "device_id": "sensor-A", "event_type": "telemetry",
        "observed_at": "2026-09-04T10:00:00Z", "sequence": 7,
        "metrics": {"temperature": 22.5},
    }

    first = client.post("/api/v1/live/telemetry", json=payload,
                        headers={"X-Traceveil-Source-Token": VALID_TOKEN})
    assert first.status_code == 202
    assert first.json()["duplicate"] is False
    original_receipt_id = first.json()["receipt_id"]
    assert _wait_receipt(client, original_receipt_id)["status"] == "completed"

    # Replay the exact same (source_id, sequence). Response still says
    # duplicate=true (unchanged contract), but a new audit row appears.
    replay = client.post("/api/v1/live/telemetry", json=payload,
                         headers={"X-Traceveil-Source-Token": VALID_TOKEN})
    assert replay.status_code == 202
    assert replay.json()["duplicate"] is True
    assert replay.json()["receipt_id"] == original_receipt_id

    audit = _audit_actions(client, cid)
    replays = [row for row in audit if row["action"] == "live.replay_detected"]
    assert len(replays) == 1
    row = replays[0]
    assert row["subject_type"] == "live_receipt"
    assert row["subject_id"] == original_receipt_id
    assert row["details"]["source_id"] == "live-lab-01"
    assert row["details"]["sequence"] == 7
    assert row["details"]["original_receipt_id"] == original_receipt_id


def test_replay_records_one_audit_per_attempt(client):
    cid = _make_case(client)
    _make_session(client, cid, ["live-lab-01"])
    payload = {
        "schema_version": "1.0", "case_id": cid, "source_id": "live-lab-01",
        "device_id": "sensor-A", "event_type": "telemetry",
        "observed_at": "2026-09-04T10:00:00Z", "sequence": 3,
        "metrics": {"temperature": 20.0},
    }
    first = client.post("/api/v1/live/telemetry", json=payload,
                        headers={"X-Traceveil-Source-Token": VALID_TOKEN})
    _wait_receipt(client, first.json()["receipt_id"])

    for _ in range(3):
        client.post("/api/v1/live/telemetry", json=payload,
                    headers={"X-Traceveil-Source-Token": VALID_TOKEN})

    replays = [r for r in _audit_actions(client, cid) if r["action"] == "live.replay_detected"]
    assert len(replays) == 3


# ---------------------------------------------------------------------------
# TV5-12 - auth failure audit
# ---------------------------------------------------------------------------
def _list_auth_failure_audits(client, case_id: int) -> list[dict]:
    """Auth failures are recorded with case_id=NULL. Read them directly
    from the service's DB rather than the case-scoped audit endpoint."""
    svc = client.app.state.phase3_service
    rows = svc.db.execute(
        "SELECT * FROM audit_events WHERE action='live.auth_failure' ORDER BY occurred_at"
    ).fetchall()
    import json as _json
    return [
        {**dict(r), "details": _json.loads(r["details_json"] or "{}")}
        for r in rows
    ]


def test_invalid_token_with_valid_body_writes_one_audit_row(client):
    cid = _make_case(client)
    _make_session(client, cid, ["live-lab-01"])
    payload = {
        "schema_version": "1.0", "case_id": cid, "source_id": "live-lab-01",
        "device_id": "d", "event_type": "telemetry",
        "observed_at": "2026-09-04T10:00:00Z", "sequence": 1,
        "metrics": {"temperature": 20.0},
    }
    response = client.post("/api/v1/live/telemetry", json=payload,
                           headers={"X-Traceveil-Source-Token": "wrong-token"})
    assert response.status_code == 401

    rows = _list_auth_failure_audits(client, cid)
    assert len(rows) == 1
    row = rows[0]
    assert row["actor"] == "system"
    assert row["details"]["reason"] == "invalid_token"
    assert row["details"]["source_id"] == "live-lab-01"
    # Never stores the presented token or unbounded caller input.
    assert "wrong-token" not in row["details_json"]


def test_rogue_source_and_bad_token_still_produces_audit(client):
    """Body carries source_id 'rogue-node-01' which is not in
    LIVE_SOURCE_TOKENS. Endpoint must still write a bounded audit row."""
    payload = {
        "schema_version": "1.0", "case_id": 1, "source_id": "rogue-node-01",
        "device_id": "rogue", "event_type": "telemetry",
        "observed_at": "2026-09-04T10:00:00Z", "sequence": 0,
        "metrics": {"temperature": 20.0},
    }
    response = client.post("/api/v1/live/telemetry", json=payload,
                           headers={"X-Traceveil-Source-Token": "anything"})
    assert response.status_code == 401

    rows = _list_auth_failure_audits(client, 1)
    assert any(r["details"].get("source_id") == "rogue-node-01"
               and r["details"]["reason"] == "invalid_token"
               for r in rows)


def test_missing_source_id_is_recorded_as_missing_source_id(client):
    """A body that JSON-parses to something without a string source_id
    still yields one audit row - reason 'missing_source_id'."""
    response = client.post("/api/v1/live/telemetry",
                           json={"not_a_valid": "envelope"},
                           headers={"X-Traceveil-Source-Token": "anything"})
    assert response.status_code == 401

    rows = _list_auth_failure_audits(client, None)
    assert any(r["details"]["reason"] == "missing_source_id" for r in rows)


def test_auth_failure_source_id_with_invalid_shape_is_sanitized(client):
    """A source_id containing whitespace/path traversal must NOT reach
    the audit row unmodified; it should be recorded as 'invalid_format'."""
    payload = {
        "schema_version": "1.0", "case_id": 1,
        "source_id": "../etc/passwd",           # not [A-Za-z0-9._:-]{1,128}
        "device_id": "d", "event_type": "telemetry",
        "observed_at": "2026-09-04T10:00:00Z", "sequence": 1,
        "metrics": {"temperature": 20.0},
    }
    # This body fails LiveTelemetryInput validation (source_id regex),
    # so the endpoint takes the malformed-body branch AND finds an
    # invalid source_id string, then verify_source rejects it.
    response = client.post("/api/v1/live/telemetry", json=payload,
                           headers={"X-Traceveil-Source-Token": "anything"})
    assert response.status_code == 401

    rows = _list_auth_failure_audits(client, 1)
    assert any(r["details"].get("source_id") == "invalid_format" for r in rows)
    # And the raw attacker string never appears in stored audit details.
    for r in rows:
        assert "etc/passwd" not in r["details_json"]


def test_auth_failure_audit_is_rate_limited(client, monkeypatch):
    """A flood of bad-token requests from the same source_id must not
    fill audit_events. After the configured cap per minute is reached,
    further failures are dropped silently (but the HTTP 401 stays)."""
    # Tighten the cap to keep the test fast.
    svc = client.app.state.phase3_service
    svc.settings.live_auth_failure_audit_per_minute = 3

    payload_template = {
        "schema_version": "1.0", "case_id": 1, "source_id": "live-lab-01",
        "device_id": "d", "event_type": "telemetry",
        "observed_at": "2026-09-04T10:00:00Z",
        "metrics": {"temperature": 20.0},
    }
    for i in range(10):
        p = dict(payload_template, sequence=i)
        r = client.post("/api/v1/live/telemetry", json=p,
                        headers={"X-Traceveil-Source-Token": "wrong"})
        assert r.status_code == 401   # HTTP behavior unchanged

    rows = [r for r in _list_auth_failure_audits(client, None)
            if r["details"].get("source_id") == "live-lab-01"]
    assert len(rows) == 3, f"expected 3 audit rows, got {len(rows)}"
