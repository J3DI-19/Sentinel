from app.evidence.schemas import EvidenceSource
from time import sleep


def create_case(client):
    response = client.post("/api/v1/cases", json={"name": "Batch demo", "description": "Phase 2"})
    assert response.status_code == 201
    return response.json()["id"]


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
