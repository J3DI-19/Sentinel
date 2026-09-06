from pathlib import Path
from time import sleep

from app.evidence.schemas import EvidenceSource


def create_case(client):
    response = client.post("/api/v1/cases", json={"name": "Batch demo", "description": "Phase 2"})
    assert response.status_code == 201
    return response.json()["id"]


def test_case_creation_trims_fields_and_rejects_blank_names(client):
    response = client.post(
        "/api/v1/cases",
        json={"name": "  Batch review  ", "description": "  Showcase case  ", "owner": "  Reviewer  "},
    )
    assert response.status_code == 201
    assert response.json()["name"] == "Batch review"
    assert response.json()["description"] == "Showcase case"
    assert response.json()["owner"] == "Reviewer"
    listed = client.get("/api/v1/cases?page=1&page_size=100").json()
    assert listed["items"][0]["id"] == response.json()["id"]

    blank = client.post("/api/v1/cases", json={"name": "   "})
    assert blank.status_code == 422
    assert blank.json()["code"] == "request_validation_error"

    oversized = client.post("/api/v1/cases", json={"name": "x" * 201})
    assert oversized.status_code == 422


def upload(client, case_id, content, *, source="simulation", filename="events.csv"):
    return client.post(
        f"/api/v1/cases/{case_id}/imports",
        data={"source_type": source, "timezone": "UTC"},
        files={"file": (filename, content, "text/csv")},
    )


def wait_for(client, import_id, states):
    for _ in range(100):
        job = client.get(f"/api/v1/imports/{import_id}").json()
        if job["state"] in states: return job
        sleep(0.01)
    raise AssertionError(f"import {import_id} did not reach {states}")


def test_valid_import_is_persisted_and_queryable(client):
    case_id = create_case(client)
    response = upload(
        client,
        case_id,
        b"timestamp,device_id,event_type\n2026-01-01T00:00:00Z,sensor-1,motion\n",
    )
    assert response.status_code == 202
    job = wait_for(client, response.json()["import_id"], {"awaiting_commit"})
    assert job["state"] == "awaiting_commit"
    assert job["validation"]["accepted_records"] == 1

    committed = client.post(
        f"/api/v1/imports/{job['import_id']}/commit", json={"allow_partial": False}
    )
    assert committed.status_code == 202
    assert wait_for(client, job["import_id"], {"completed"})["state"] == "completed"

    evidence = client.get(f"/api/v1/cases/{case_id}/evidence").json()
    events = client.get(f"/api/v1/cases/{case_id}/events").json()
    assert evidence["total"] == 1
    assert events["total"] == 1
    assert events["items"][0]["provenance"]["source_type"] == "simulation"
    assert events["items"][0]["ingested_at"] == job["validation"]["metadata"]["received_at"]


def test_partial_import_requires_explicit_approval(client):
    case_id = create_case(client)
    response = upload(
        client,
        case_id,
        b"timestamp,device_id,event_type\n2026-01-01T00:00:00Z,sensor-1,motion\nnot-a-time,sensor-2,motion\n",
    )
    job = wait_for(client, response.json()["import_id"], {"awaiting_commit"})
    assert job["validation"]["accepted_records"] == 1
    assert job["validation"]["rejected_records"] == 1

    refused = client.post(
        f"/api/v1/imports/{job['import_id']}/commit", json={"allow_partial": False}
    )
    assert refused.status_code == 409
    assert refused.json()["code"] == "partial_confirmation_required"

    accepted = client.post(
        f"/api/v1/imports/{job['import_id']}/commit", json={"allow_partial": True}
    )
    assert accepted.status_code == 202
    assert wait_for(client, job["import_id"], {"partial_success"})["state"] == "partial_success"


def test_duplicate_hash_does_not_create_more_events(client):
    case_id = create_case(client)
    body = b"timestamp,device_id,event_type\n2026-01-01T00:00:00Z,sensor-1,motion\n"
    first_upload = upload(client, case_id, body).json()
    first = wait_for(client, first_upload["import_id"], {"awaiting_commit"})
    client.post(f"/api/v1/imports/{first['import_id']}/commit", json={"allow_partial": False})
    wait_for(client, first["import_id"], {"completed"})

    duplicate = upload(client, case_id, body).json()
    assert duplicate["state"] == "duplicate"
    assert duplicate["evidence_id"] == first["evidence_id"]
    assert client.get(f"/api/v1/cases/{case_id}/events").json()["total"] == 1


def test_primary_adapter_schemas_validate(client):
    case_id = create_case(client)
    casas_upload = upload(
        client,
        case_id,
        b"timestamp,sensor_id,message,activity\n2026-01-01T00:00:00Z,M001,ON,Cook\n",
        source=EvidenceSource.CASAS.value,
        filename="casas.csv",
    )
    casas = wait_for(client, casas_upload.json()["import_id"], {"awaiting_commit"})
    assert casas["validation"]["accepted_records"] == 1

    ton_upload = upload(
        client,
        case_id,
        b"ts,label,type,device_id,temperature\n2026-01-01T00:00:00Z,normal,fridge,fridge-1,4.2\n",
        source=EvidenceSource.TON_IOT_TELEMETRY.value,
        filename="ton.csv",
    )
    ton = wait_for(client, ton_upload.json()["import_id"], {"awaiting_commit"})
    assert ton["validation"]["accepted_records"] == 1


def test_pagination_is_bounded_and_errors_have_request_ids(client):
    create_case(client)
    invalid = client.get("/api/v1/cases?page_size=1000")
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "request_validation_error"
    assert invalid.json()["request_id"]
    missing = client.get("/api/v1/cases/99999")
    assert missing.status_code == 404
    assert missing.headers["x-request-id"] == missing.json()["request_id"]


def test_public_upload_reports_malformed_and_oversized_evidence(small_upload_client):
    case_id = create_case(small_upload_client)
    malformed = upload(
        small_upload_client,
        case_id,
        b"\xff\xfe\x00",
        filename="malformed.csv",
    ).json()
    malformed_job = wait_for(
        small_upload_client, malformed["import_id"], {"rejected"}
    )
    assert malformed_job["error"] is None
    assert "INVALID_ENCODING" in {
        issue["code"] for issue in malformed_job["validation"]["issues"]
    }

    oversized = upload(
        small_upload_client,
        case_id,
        b"x" * 129,
        filename="oversized.csv",
    ).json()
    oversized_job = wait_for(
        small_upload_client, oversized["import_id"], {"rejected"}
    )
    assert "FILE_TOO_LARGE" in {
        issue["code"] for issue in oversized_job["validation"]["issues"]
    }


def test_commit_rejects_evidence_changed_after_validation(client):
    case_id = create_case(client)
    uploaded = upload(
        client,
        case_id,
        b"timestamp,device_id,event_type\n2026-01-01T00:00:00Z,sensor-1,motion\n",
    ).json()
    job = wait_for(client, uploaded["import_id"], {"awaiting_commit"})
    stored_job = client.app.state.batch_service.get_import(job["import_id"])
    Path(stored_job["file_path"]).write_bytes(
        b"timestamp,device_id,event_type\n2026-01-01T00:00:00Z,sensor-9,command\n"
    )

    response = client.post(
        f"/api/v1/imports/{job['import_id']}/commit",
        json={"allow_partial": False},
    )
    assert response.status_code == 202
    failed = wait_for(client, job["import_id"], {"failed"})
    assert failed["error"]["code"] == "evidence_content_hash_mismatch"
    assert client.get(f"/api/v1/cases/{case_id}/evidence").json()["total"] == 0
    assert client.get(f"/api/v1/cases/{case_id}/events").json()["total"] == 0
    assert client.get(f"/api/v1/cases/{case_id}/analyses").json()["total"] == 0


def test_failed_analysis_commit_can_retry_the_same_evidence(client, monkeypatch):
    case_id = create_case(client)
    body = (
        b"timestamp,device_id,event_type,label\n"
        b"2026-01-01T00:00:00Z,sensor-1,motion,malicious\n"
    )
    uploaded = upload(client, case_id, body).json()
    job = wait_for(client, uploaded["import_id"], {"awaiting_commit"})
    analyzer = client.app.state.batch_service.analyzer
    original_analyze = analyzer.analyze

    def fail_analysis(**_kwargs):
        raise RuntimeError("forced analysis failure")

    monkeypatch.setattr(analyzer, "analyze", fail_analysis)
    client.post(
        f"/api/v1/imports/{job['import_id']}/commit",
        json={"allow_partial": False},
    )
    failed = wait_for(client, job["import_id"], {"failed"})

    assert failed["error"]["code"] == "commit_failed"
    assert client.get(f"/api/v1/cases/{case_id}/evidence").json()["total"] == 0
    assert client.get(f"/api/v1/cases/{case_id}/events").json()["total"] == 0
    assert client.get(f"/api/v1/cases/{case_id}/analyses").json()["total"] == 0

    monkeypatch.setattr(analyzer, "analyze", original_analyze)
    retried = upload(client, case_id, body).json()
    assert retried["state"] != "duplicate"
    retry_job = wait_for(client, retried["import_id"], {"awaiting_commit"})
    client.post(
        f"/api/v1/imports/{retry_job['import_id']}/commit",
        json={"allow_partial": False},
    )
    assert wait_for(client, retry_job["import_id"], {"completed"})["state"] == "completed"
    assert client.get(f"/api/v1/cases/{case_id}/evidence").json()["total"] == 1
    assert client.get(f"/api/v1/cases/{case_id}/events").json()["total"] == 1
    assert client.get(f"/api/v1/cases/{case_id}/analyses").json()["total"] == 1


def test_analysis_history_details_charts_and_reanalysis_are_idempotent(client):
    case_id = create_case(client)
    authentication_rows = "".join(
        f"2026-01-01T00:00:{second:02d}Z,camera-1,authentication_failure,185.77.12.44,authenticate,denied\n"
        for second in range(10)
    )
    uploaded = upload(
        client,
        case_id,
        (
            "timestamp,device_id,event_type,source_ip,action,outcome\n"
            + authentication_rows
        ).encode(),
        filename="authentication.csv",
    ).json()
    job = wait_for(client, uploaded["import_id"], {"awaiting_commit"})
    client.post(
        f"/api/v1/imports/{job['import_id']}/commit",
        json={"allow_partial": False},
    )
    wait_for(client, job["import_id"], {"completed"})

    evidence = client.get(f"/api/v1/cases/{case_id}/evidence").json()["items"][0]
    event = client.get(f"/api/v1/cases/{case_id}/events").json()["items"][0]
    assert event["provenance"]["evidence_id"] == job["evidence_id"]
    assert event["provenance"]["source_record_reference"]
    assert event["provenance"]["raw_record_hash"]
    assert client.get(
        f"/api/v1/cases/{case_id}/evidence/{evidence['evidence_id']}"
    ).status_code == 200
    assert client.get(
        f"/api/v1/cases/{case_id}/events/{event['event_id']}"
    ).status_code == 200

    first_history = client.get(f"/api/v1/cases/{case_id}/analyses").json()
    assert first_history["total"] == 1
    analysis_id = first_history["items"][0]["analysis_id"]
    assert first_history["items"][0]["is_latest"] is True
    assert len(first_history["items"][0]["input_fingerprint"]) == 64
    assert first_history["items"][0]["input_event_count"] == 10
    assert first_history["items"][0]["finding_count"] >= 1
    assert first_history["items"][0]["incident_count"] >= 1

    newer_upload = upload(
        client,
        case_id,
        b"timestamp,device_id,event_type\n2026-01-01T00:01:00Z,sensor-2,motion\n",
        filename="newer.csv",
    ).json()
    newer_job = wait_for(client, newer_upload["import_id"], {"awaiting_commit"})
    client.post(
        f"/api/v1/imports/{newer_job['import_id']}/commit",
        json={"allow_partial": False},
    )
    wait_for(client, newer_job["import_id"], {"completed"})

    history = client.get(f"/api/v1/cases/{case_id}/analyses").json()
    assert history["total"] == 2
    latest_analysis_id = history["items"][0]["analysis_id"]
    assert latest_analysis_id != analysis_id
    assert history["items"][0]["is_latest"] is True
    assert history["items"][1]["is_latest"] is False
    latest = client.get(f"/api/v1/cases/{case_id}/analyses/latest")
    historical = client.get(
        f"/api/v1/cases/{case_id}/analyses/{analysis_id}"
    )
    assert latest.status_code == historical.status_code == 200
    assert latest.json()["analysis_id"] == latest_analysis_id
    assert historical.json()["analysis_id"] == analysis_id
    historical_result = historical.json()
    assert historical_result["incidents"]
    finding = historical_result["findings"][0]
    assert len(finding["risk"]["factors"]) == 5
    assert finding["evidence_ids"] == [job["evidence_id"]]
    assert finding["event_ids"]
    assert historical_result["timeline"]
    assert historical_result["graph"]["nodes"]
    assert historical_result["chart_points"]

    for resource in ("findings", "alerts", "incidents", "timeline", "aggregates", "charts"):
        selected = client.get(
            f"/api/v1/cases/{case_id}/{resource}", params={"analysis_id": analysis_id}
        )
        assert selected.status_code == 200
    selected_graph = client.get(
        f"/api/v1/cases/{case_id}/graph", params={"analysis_id": analysis_id}
    )
    assert selected_graph.status_code == 200
    assert client.get(
        f"/api/v1/cases/{case_id}/incidents", params={"analysis_id": analysis_id}
    ).json()["total"] >= 1

    first = client.post(f"/api/v1/cases/{case_id}/analyses").json()
    second = client.post(f"/api/v1/cases/{case_id}/analyses").json()
    assert first["analysis_id"] == second["analysis_id"] == latest_analysis_id
    assert first["outcome"] == second["outcome"] == "reused"
    assert first["reused_existing"] is second["reused_existing"] is True
    assert first["created_at"] == second["created_at"] == history["items"][0]["created_at"]
    assert client.get(f"/api/v1/cases/{case_id}/analyses").json()["total"] == 2


def test_reanalysis_reports_created_then_reused_without_duplicate_artifacts(client):
    case_id = create_case(client)

    created = client.post(f"/api/v1/cases/{case_id}/analyses")
    reused = client.post(f"/api/v1/cases/{case_id}/analyses")

    assert created.status_code == reused.status_code == 202
    assert created.json()["outcome"] == "created"
    assert reused.json()["outcome"] == "reused"
    assert reused.json()["analysis_id"] == created.json()["analysis_id"]
    assert reused.json()["created_at"] == created.json()["created_at"]
    assert client.get(f"/api/v1/cases/{case_id}/analyses").json()["total"] == 1
    assert client.get(f"/api/v1/cases/{case_id}/findings").json()["total"] == 0


def test_custom_analysis_configuration_is_explicitly_rejected(client):
    case_id = create_case(client)
    response = client.post(
        f"/api/v1/cases/{case_id}/analyses",
        json={"authentication_failure_threshold": 3},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "request_validation_error"
