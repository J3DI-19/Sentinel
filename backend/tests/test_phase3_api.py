from time import sleep

import pytest


def case_id(client):
    return client.post("/api/v1/cases", json={"name": "Live demo"}).json()["id"]


def wait_receipt(client, receipt_id):
    for _ in range(200):
        result = client.get(f"/api/v1/live/receipts/{receipt_id}").json()
        if result["status"] in {"completed", "failed", "rejected"}:
            return result
        sleep(0.01)
    raise AssertionError("live receipt did not complete")


def test_authenticated_live_telemetry_is_persisted_and_streamed(client):
    cid = case_id(client)
    session = client.post(
        f"/api/v1/cases/{cid}/live-sessions",
        json={"label": "Lab", "source_ids": ["live-lab-01"]},
    )
    assert session.status_code == 201
    sid = session.json()["session_id"]
    payload = {
        "schema_version": "1.0", "case_id": cid, "source_id": "live-lab-01",
        "device_id": "sensor-1", "event_type": "telemetry",
        "observed_at": "2026-08-15T10:00:00Z", "sequence": 1,
        "metrics": {"temperature": 24.5},
    }
    unauthorized = client.post("/api/v1/live/telemetry", json=payload, headers={"X-Traceveil-Source-Token": "wrong"})
    assert unauthorized.status_code == 401
    accepted = client.post("/api/v1/live/telemetry", json=payload, headers={"X-Traceveil-Source-Token": "traceveil-demo-token"})
    assert accepted.status_code == 202
    receipt = wait_receipt(client, accepted.json()["receipt_id"])
    assert receipt["status"] == "completed"

    duplicate = client.post("/api/v1/live/telemetry", json=payload, headers={"X-Traceveil-Source-Token": "traceveil-demo-token"})
    assert duplicate.json()["duplicate"] is True
    events = client.get(f"/api/v1/cases/{cid}/events?origin=live").json()
    assert events["total"] == 1
    devices = client.get(f"/api/v1/cases/{cid}/live/devices?session_id={sid}").json()
    assert devices["items"][0]["latest_metrics"] == {"temperature": 24.5}
    messages = []
    for _ in range(300):
        messages = client.app.state.phase3_service.stream_after(0, cid, sid, [])
        if "metrics.updated" in {item["topic"] for item in messages}:
            break
        sleep(0.01)
    assert {item["topic"] for item in messages} >= {"event.accepted", "device.updated", "metrics.updated"}


def test_malformed_live_payload_is_counted_without_an_event(client):
    cid = case_id(client)
    client.post(f"/api/v1/cases/{cid}/live-sessions", json={"source_ids": ["live-lab-01"]})
    response = client.post(
        "/api/v1/live/telemetry",
        json={"schema_version": "1.0", "case_id": cid, "source_id": "live-lab-01"},
        headers={"X-Traceveil-Source-Token": "traceveil-demo-token"},
    )
    assert response.status_code == 409
    metrics = client.get(f"/api/v1/cases/{cid}/live/metrics").json()
    assert metrics["malformed_count"] == 1
    assert client.get(f"/api/v1/cases/{cid}/events?origin=live").json()["total"] == 0


def test_report_approval_and_email_content_hash_lifecycle(client):
    cid = case_id(client)
    created = client.post(f"/api/v1/cases/{cid}/reports", json={"title": "Demo report"}).json()
    generated = client.post(f"/api/v1/reports/{created['report_id']}/generate").json()
    assert generated["status"] == "generated"
    exported = client.get(f"/api/v1/reports/{created['report_id']}/export")
    assert exported.status_code == 200
    assert exported.content.startswith(b"%PDF")
    approved = client.post(f"/api/v1/reports/{created['report_id']}/approve", json={"approver": "Investigator", "confirmed": True}).json()
    assert approved["status"] == "approved"
    version = client.app.state.phase3_service.db.execute("SELECT * FROM report_versions WHERE report_id=?", (created["report_id"],)).fetchone()
    assert version["content_hash"] == approved["content_hash"]
    assert version["approved_by"] == "Investigator"
    draft = client.post(f"/api/v1/reports/{created['report_id']}/email-drafts", json={"recipient": "security@example.test", "subject": "Report", "body": "Approved report attached."}).json()
    approved_draft = client.post(f"/api/v1/email-drafts/{draft['draft_id']}/approve", json={"approver": "Investigator", "confirmed": True}).json()
    assert approved_draft["status"] == "approved"
    edited = client.patch(f"/api/v1/email-drafts/{draft['draft_id']}", json={"recipient": "security@example.test", "subject": "Updated", "body": "Changed."}).json()
    assert edited["status"] == "draft"
    assert edited["approved_at"] is None


def test_controlled_live_authentication_sequence_creates_persisted_alert(client):
    cid = case_id(client)
    client.post(f"/api/v1/cases/{cid}/live-sessions", json={"source_ids": ["live-lab-01"]})
    for sequence in range(10):
        payload = {
            "schema_version": "1.0", "case_id": cid, "source_id": "live-lab-01",
            "device_id": "door-controller", "event_type": "authentication",
            "observed_at": f"2026-08-15T10:00:{sequence:02d}Z", "sequence": sequence,
            "metrics": {"action": "authenticate", "outcome": "failed"},
        }
        accepted = client.post("/api/v1/live/telemetry", json=payload, headers={"X-Traceveil-Source-Token": "traceveil-demo-token"})
        assert accepted.status_code == 202
        assert wait_receipt(client, accepted.json()["receipt_id"])["status"] == "completed"
    alerts = []
    for _ in range(300):
        alerts = client.get(f"/api/v1/cases/{cid}/alerts").json()["items"]
        if any(item["rule_id"] == "AUTH-001" for item in alerts):
            break
        sleep(0.01)
    assert any(item["rule_id"] == "AUTH-001" for item in alerts)
    history = client.get(f"/api/v1/cases/{cid}/analyses").json()
    assert history["total"] >= 1
    analysis_id = history["items"][0]["analysis_id"]
    persisted_alerts = client.get(
        f"/api/v1/cases/{cid}/alerts", params={"analysis_id": analysis_id}
    ).json()
    assert any(item["rule_id"] == "AUTH-001" for item in persisted_alerts["items"])
    assert client.get(
        f"/api/v1/cases/{cid}/timeline", params={"analysis_id": analysis_id}
    ).json()["total"] >= 1


def test_assistant_offline_is_retryable_and_does_not_affect_core(client):
    cid = case_id(client)
    session = client.post("/api/v1/assistant/sessions", json={"scope": "specific_case", "case_ids": [cid]}).json()
    job = client.post(f"/api/v1/assistant/sessions/{session['session_id']}/messages", json={"question": "Summarize this case"}).json()
    for _ in range(200):
        current = client.get(f"/api/v1/assistant/jobs/{job['job_id']}").json()
        if current["status"] in {"completed", "failed"}:
            break
        sleep(0.01)
    assert current["status"] == "failed"
    assert current["error"]["code"] == "ollama_offline"
    assert current["error"]["retryable"] is True
    assert client.get(f"/api/v1/cases/{cid}").status_code == 200


def test_assistant_rejects_unretrieved_citations_numbers_and_layout_data(client):
    service = client.app.state.phase3_service
    context = {"allowed_refs": ["case:1"], "facts": [{"ref": "case:1", "data": {"event_count": 3}}]}
    with pytest.raises(ValueError, match="invalid_assistant_citation"):
        service._validate_assistant_result({"answer": "Review the case.", "citations": ["case:999"], "visualization": None}, context)
    with pytest.raises(ValueError, match="invented_numeric_claim"):
        service._validate_assistant_result({"answer": "There were 99 events.", "citations": ["case:1"], "visualization": None}, context)
    with pytest.raises(ValueError, match="embedded_visualization_data"):
        service._validate_assistant_result({"answer": "There were 3 events.", "citations": ["case:1"], "visualization": {"schema_version": "1.0", "component": "event_activity", "data_ref": "case:1", "values": [3]}}, context)
    with pytest.raises(ValueError, match="unsafe_assistant_answer"):
        service._validate_assistant_result({"answer": "Follow https://untrusted.invalid", "citations": [], "visualization": None}, context)


def test_fake_smtp_delivery_is_explicit_audited_and_idempotent(client, monkeypatch):
    cid = case_id(client); service = client.app.state.phase3_service
    report = client.post(f"/api/v1/cases/{cid}/reports", json={"title": "SMTP test"}).json()
    client.post(f"/api/v1/reports/{report['report_id']}/generate")
    client.post(f"/api/v1/reports/{report['report_id']}/approve", json={"approver": "Investigator", "confirmed": True})
    draft = client.post(f"/api/v1/reports/{report['report_id']}/email-drafts", json={"recipient": "security@example.test", "subject": "Approved report", "body": "Attached."}).json()
    client.post(f"/api/v1/email-drafts/{draft['draft_id']}/approve", json={"approver": "Investigator", "confirmed": True})
    service.settings.smtp_host = "smtp.test"; service.settings.smtp_from_address = "traceveil@example.test"; service.settings.smtp_starttls = False; service.settings.smtp_allowed_recipient_domains = ["example.test"]
    sent = []
    class FakeSMTP:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def send_message(self, message): sent.append(message)
    monkeypatch.setattr("app.services.phase3.smtplib.SMTP", FakeSMTP)
    first_response = client.post(f"/api/v1/email-drafts/{draft['draft_id']}/send")
    assert first_response.status_code == 200, first_response.text
    second_response = client.post(f"/api/v1/email-drafts/{draft['draft_id']}/send")
    assert second_response.status_code == 200, second_response.text
    first = first_response.json(); second = second_response.json()
    assert first["status"] == second["status"] == "sent"
    assert len(sent) == 1
    audit = client.get(f"/api/v1/cases/{cid}/audit").json()["items"]
    assert any(item["action"] == "email.sent" and item["request_id"] for item in audit)
