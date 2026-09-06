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

import concurrent.futures
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
    """Polls a receipt until it reaches a terminal status. On any
    unexpected shape (e.g. a 404 error body with no 'status' key) it
    raises AssertionError showing the HTTP status and body, instead of a
    bare KeyError('status') that hides what actually went wrong."""
    last = None
    for _ in range(300):
        response = client.get(f"/api/v1/live/receipts/{receipt_id}")
        try:
            body = response.json()
        except ValueError:
            body = {"_raw": response.text}
        last = (response.status_code, body)
        if response.status_code != 200:
            raise AssertionError(
                f"receipt {receipt_id} GET returned HTTP {response.status_code}: {body}"
            )
        status = body.get("status")
        if status is None:
            raise AssertionError(
                f"receipt {receipt_id} response has no 'status' field: {body}"
            )
        if status in {"completed", "failed", "rejected"}:
            return body
        sleep(0.01)
    raise AssertionError(f"live receipt {receipt_id} did not reach a terminal status; last={last}")


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


def _telemetry(cid, seq, temp=20.0, source="live-lab-01"):
    return {
        "schema_version": "1.0", "case_id": cid, "source_id": source,
        "device_id": "sensor-A", "event_type": "telemetry",
        "observed_at": "2026-09-04T10:00:00Z", "sequence": seq,
        "metrics": {"temperature": temp},
    }


def _post(client, payload):
    return client.post("/api/v1/live/telemetry", json=payload,
                       headers={"X-Traceveil-Source-Token": VALID_TOKEN})


# TV5-11 - high-water sequence-regression: 100 -> 99 is detected
def test_lower_unseen_sequence_is_regression_not_accepted(client):
    cid = _make_case(client)
    _make_session(client, cid, ["live-lab-01"])
    accepted = _post(client, _telemetry(cid, 100))
    assert accepted.status_code == 202
    _wait_receipt(client, accepted.json()["receipt_id"])

    # A previously unseen lower sequence must be rejected as a regression.
    regressed = _post(client, _telemetry(cid, 99, temp=21.0))
    assert regressed.status_code == 409
    assert regressed.json()["code"] == "live_sequence_regression"

    audit = _audit_actions(client, cid)
    regs = [r for r in audit if r["action"] == "live.sequence_regression"]
    assert len(regs) == 1
    assert regs[0]["details"]["sequence"] == 99
    assert regs[0]["details"]["high_water_sequence"] == 100

    # No canonical event was created for the regressed frame.
    events = client.get(f"/api/v1/cases/{cid}/events?origin=live").json()
    assert events["total"] == 1  # only the seq=100 frame

    # The regression is quarantined in live_ingest_issues.
    svc = client.app.state.phase3_service
    issues = svc.db.execute(
        "SELECT code FROM live_ingest_issues WHERE source_id='live-lab-01'"
    ).fetchall()
    assert any(r["code"] == "sequence_regression" for r in issues)


def test_same_sequence_different_payload_is_collision(client):
    cid = _make_case(client)
    _make_session(client, cid, ["live-lab-01"])
    accepted = _post(client, _telemetry(cid, 50, temp=20.0))
    assert accepted.status_code == 202
    _wait_receipt(client, accepted.json()["receipt_id"])

    # Same sequence, different content -> collision (possible tampering).
    collision = _post(client, _telemetry(cid, 50, temp=99.9))
    assert collision.status_code == 409
    assert collision.json()["code"] == "live_sequence_collision"

    cols = [r for r in _audit_actions(client, cid) if r["action"] == "live.sequence_collision"]
    assert len(cols) == 1
    assert cols[0]["details"]["attempted_payload_hash"] != cols[0]["details"]["original_payload_hash"]


def test_exact_duplicate_still_returns_original_receipt(client):
    cid = _make_case(client)
    _make_session(client, cid, ["live-lab-01"])
    first = _post(client, _telemetry(cid, 5))
    _wait_receipt(client, first.json()["receipt_id"])

    dup = _post(client, _telemetry(cid, 5))          # identical bytes
    assert dup.status_code == 202
    assert dup.json()["duplicate"] is True
    assert dup.json()["receipt_id"] == first.json()["receipt_id"]


def test_high_water_persists_across_sessions(client):
    cid = _make_case(client)
    sid1 = _make_session(client, cid, ["live-lab-01"])
    a = _post(client, _telemetry(cid, 200))
    _wait_receipt(client, a.json()["receipt_id"])
    client.post(f"/api/v1/live-sessions/{sid1}/stop")

    # New session, same source: a lower sequence is still a regression
    # because the high-water mark is tracked at source level.
    _make_session(client, cid, ["live-lab-01"])
    regressed = _post(client, _telemetry(cid, 150, temp=21.0))
    assert regressed.status_code == 409
    assert regressed.json()["code"] == "live_sequence_regression"

    # But a higher sequence in the new session is accepted.
    higher = _post(client, _telemetry(cid, 201))
    assert higher.status_code == 202
    _wait_receipt(client, higher.json()["receipt_id"])


def test_concurrent_submissions_cannot_slip_a_lower_sequence(client):
    """Fire many frames at the same source concurrently, including
    interleaved high and low sequences. Because classification + insert +
    high-water update are one atomic transaction, the final high-water is
    the maximum accepted sequence and every accepted sequence is unique -
    no lower sequence slips through behind a higher one."""
    cid = _make_case(client)
    _make_session(client, cid, ["live-lab-01"])
    # Raise the per-source rate limit so this test exercises sequence
    # atomicity, not the (separate) rate limiter.
    client.app.state.phase3_service.settings.live_rate_limit_per_second = 10000

    # Interleave ascending and descending sequences to maximise the chance
    # of a lost-update race if the check were not atomic.
    sequences = []
    for i in range(1, 26):
        sequences.append(i)
        sequences.append(51 - i)   # 50, 49, ... interleaved

    def submit(s):
        r = _post(client, _telemetry(cid, s, temp=float(s)))
        return s, r.status_code

    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for s, code in pool.map(submit, sequences):
            results.setdefault(code, 0)
            results[code] += 1

    # Every request resolved to a defined outcome (no 500s / crashes).
    assert set(results) <= {202, 409}, f"unexpected status codes: {results}"

    svc = client.app.state.phase3_service
    # Exactly one accepted receipt per distinct sequence value (no double
    # accept of the same sequence, no torn inserts).
    rows = svc.db.execute(
        "SELECT sequence, COUNT(*) c FROM live_receipts WHERE source_id='live-lab-01' GROUP BY sequence"
    ).fetchall()
    for r in rows:
        assert r["c"] == 1, f"sequence {r['sequence']} accepted {r['c']} times"

    # The stored high-water equals the largest accepted sequence.
    hw = svc.db.execute(
        "SELECT high_water_sequence FROM live_source_sequence_state WHERE source_id='live-lab-01'"
    ).fetchone()["high_water_sequence"]
    max_accepted = svc.db.execute(
        "SELECT MAX(sequence) m FROM live_receipts WHERE source_id='live-lab-01'"
    ).fetchone()["m"]
    assert hw == max_accepted

    # Any sequence below the final high-water that is NOT an accepted
    # receipt must have been rejected as a regression (quarantined), never
    # silently dropped.
    accepted_seqs = {
        r["sequence"] for r in svc.db.execute(
            "SELECT sequence FROM live_receipts WHERE source_id='live-lab-01'"
        ).fetchall()
    }
    regression_issues = svc.db.execute(
        "SELECT COUNT(*) c FROM live_ingest_issues WHERE source_id='live-lab-01' AND code='sequence_regression'"
    ).fetchone()["c"]
    missing_below_hw = [s for s in set(sequences) if s < hw and s not in accepted_seqs]
    # Each such sequence produced a regression record (they may also repeat
    # across the interleaving, so >= count of distinct missing values).
    assert regression_issues >= len(missing_below_hw)


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


def test_rotating_source_ids_from_one_ip_cannot_bypass_the_limit(client):
    """TV5-12 core: a caller rotating source_id values from a single IP
    must not be able to write more than the per-minute cap, because the
    rate-limit key is the client IP, not the (attacker-chosen) source_id."""
    svc = client.app.state.phase3_service
    svc.settings.live_auth_failure_audit_per_minute = 3

    before = len(_list_auth_failure_audits(client, None))
    # 20 requests, every one a DIFFERENT (valid-shaped) source_id, all from
    # the TestClient's single client host.
    for i in range(20):
        payload = {
            "schema_version": "1.0", "case_id": 1, "source_id": f"rot-{i:03d}",
            "device_id": "d", "event_type": "telemetry",
            "observed_at": "2026-09-04T10:00:00Z", "sequence": i,
            "metrics": {"temperature": 20.0},
        }
        r = client.post("/api/v1/live/telemetry", json=payload,
                        headers={"X-Traceveil-Source-Token": "wrong"})
        assert r.status_code == 401

    after = len(_list_auth_failure_audits(client, None))
    assert after - before == 3, f"rotating source_ids bypassed the cap: {after - before} rows"


def test_auth_failure_window_map_is_bounded(client):
    """The LRU window map must not grow past its cap even under a flood of
    distinct keys, so memory cannot be exhausted."""
    svc = client.app.state.phase3_service
    svc.auth_failure_max_keys = 8
    # Drive many distinct keys directly (bypassing HTTP for speed); each
    # unique client_ip is its own key.
    for i in range(100):
        svc.record_auth_failure(f"src-{i}", "invalid_token", client_ip=f"10.0.0.{i}")
    assert len(svc.auth_failure_windows) <= 8
