from __future__ import annotations

from uuid import uuid4


def create_case(client, name="Lab Investigation"):
    response = client.post(
        "/api/v1/cases",
        json={"name": name, "description": "Controlled test case"},
    )
    assert response.status_code == 201
    return response.json()


def ingest(client, case_id, content, *, filename="events.csv", source="simulated"):
    return client.post(
        f"/api/v1/cases/{case_id}/evidence",
        params={"filename": filename, "source_type": source},
        content=content,
        headers={"content-type": "text/csv"},
    )


def authentication_failure_csv(count=10):
    lines = [
        "timestamp,device_id,event_type,action,outcome,src_ip",
        *[
            f"2026-08-21T10:00:{index:02d}Z,CAM-01,authentication_failure,authenticate,denied,203.0.113.8"
            for index in range(count)
        ],
    ]
    return ("\n".join(lines) + "\n").encode()


def test_case_api_creates_lists_and_reads_cases(client):
    created = create_case(client)

    assert created["case_id"] == 1
    assert created["name"] == "Lab Investigation"
    assert created["status"] == "open"
    assert created["created_at"].endswith("Z")
    assert client.get("/api/v1/cases").json() == [created]
    assert client.get("/api/v1/cases/1").json() == created
    assert client.get("/api/v1/cases/999").status_code == 404


def test_case_api_rejects_blank_and_unknown_fields(client):
    blank = client.post("/api/v1/cases", json={"name": "   "})
    extra = client.post("/api/v1/cases", json={"name": "Case", "owner": "ignored?"})

    assert blank.status_code == 422
    assert extra.status_code == 422


def test_evidence_ingestion_persists_validation_event_and_provenance(client):
    case_id = create_case(client)["case_id"]
    response = ingest(
        client,
        case_id,
        b"timestamp,device_id,event_type,value\n"
        b"2026-08-21T10:00:00Z,sensor-1,telemetry,21.4\n",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["validation"]["status"] == "accepted"
    assert body["normalized_event_count"] == 1
    assert body["normalization_failures"] == []
    event = body["events"][0]
    evidence_id = body["validation"]["metadata"]["evidence_id"]
    assert event["case_id"] == case_id
    assert event["provenance"]["evidence_id"] == evidence_id
    assert event["provenance"]["source_record_reference"] == "row:1"
    assert len(event["provenance"]["source_hash"]) == 64

    evidence = client.get(f"/api/v1/cases/{case_id}/evidence").json()
    events = client.get(f"/api/v1/cases/{case_id}/events").json()
    assert evidence == [body["validation"]]
    assert events == [event]
    assert (
        client.get(f"/api/v1/cases/{case_id}/evidence/{evidence_id}").json()
        == body["validation"]
    )
    assert (
        client.get(f"/api/v1/cases/{case_id}/events/{event['event_id']}").json()
        == event
    )


def test_rejected_evidence_returns_structured_report_without_events(client):
    case_id = create_case(client)["case_id"]
    response = ingest(
        client,
        case_id,
        b"timestamp,device_id\nnot-a-time,\n",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["validation"]["status"] == "rejected"
    assert body["normalized_event_count"] == 0
    assert body["events"] == []
    assert client.get(f"/api/v1/cases/{case_id}/events").json() == []
    assert len(client.get(f"/api/v1/cases/{case_id}/evidence").json()) == 1


def test_empty_evidence_reaches_the_structured_validation_boundary(client):
    case_id = create_case(client)["case_id"]
    response = ingest(client, case_id, b"")

    assert response.status_code == 200
    body = response.json()
    assert body["validation"]["status"] == "rejected"
    assert {issue["code"] for issue in body["validation"]["issues"]} == {"EMPTY_FILE"}


def test_event_api_filters_by_type_origin_evidence_and_pages(client):
    case_id = create_case(client)["case_id"]
    response = ingest(
        client,
        case_id,
        b"timestamp,device_id,event_type\n"
        b"2026-08-21T10:00:00Z,sensor-1,telemetry\n"
        b"2026-08-21T10:00:01Z,sensor-1,device_state\n",
    )
    evidence_id = response.json()["validation"]["metadata"]["evidence_id"]

    typed = client.get(
        f"/api/v1/cases/{case_id}/events", params={"event_type": "telemetry"}
    ).json()
    batch = client.get(
        f"/api/v1/cases/{case_id}/events", params={"origin": "batch"}
    ).json()
    evidence = client.get(
        f"/api/v1/cases/{case_id}/events", params={"evidence_id": evidence_id}
    ).json()
    paged = client.get(
        f"/api/v1/cases/{case_id}/events", params={"offset": 1, "limit": 1}
    ).json()

    assert [event["event_type"] for event in typed] == ["telemetry"]
    assert len(batch) == len(evidence) == 2
    assert len(paged) == 1


def test_reanalysis_exposes_findings_incidents_timeline_graph_and_charts(client):
    case_id = create_case(client)["case_id"]
    assert ingest(client, case_id, authentication_failure_csv()).status_code == 201

    response = client.post(
        f"/api/v1/cases/{case_id}/analysis/reanalyze", json={}
    )
    assert response.status_code == 200
    analysis = response.json()
    assert analysis["input_event_count"] == 10
    assert analysis["analyzed_event_count"] == 10
    assert {finding["rule_id"] for finding in analysis["findings"]} == {"AUTH-001"}
    assert analysis["findings"][0]["risk"]["factors"]
    assert analysis["incidents"]
    assert analysis["timeline"]
    assert analysis["graph"]["nodes"]
    assert analysis["chart_points"]
    assert analysis["alerts"] == []  # Batch findings do not impersonate live alerts.

    endpoints = {
        "findings": analysis["findings"],
        "alerts": analysis["alerts"],
        "incidents": analysis["incidents"],
        "timeline": analysis["timeline"],
        "graph": analysis["graph"],
        "charts": analysis["chart_points"],
    }
    assert client.get(f"/api/v1/cases/{case_id}/analysis").json() == analysis
    for endpoint, expected in endpoints.items():
        assert client.get(f"/api/v1/cases/{case_id}/{endpoint}").json() == expected
    finding = analysis["findings"][0]
    incident = analysis["incidents"][0]
    assert client.get(
        f"/api/v1/cases/{case_id}/findings/{finding['finding_id']}"
    ).json() == finding
    assert client.get(
        f"/api/v1/cases/{case_id}/incidents/{incident['incident_id']}"
    ).json() == incident
    assert client.get(
        f"/api/v1/cases/{case_id}/alerts/{uuid4()}"
    ).status_code == 404


def test_analysis_history_and_explicit_snapshot_selection(client):
    case_id = create_case(client)["case_id"]
    ingest(client, case_id, authentication_failure_csv())
    first = client.post(
        f"/api/v1/cases/{case_id}/analysis/reanalyze", json={}
    ).json()
    second = client.post(
        f"/api/v1/cases/{case_id}/analysis/reanalyze",
        json={"filter": {"event_types": ["telemetry"]}},
    ).json()

    assert first["analysis_id"] != second["analysis_id"]
    assert second["analyzed_event_count"] == 0
    runs = client.get(f"/api/v1/cases/{case_id}/analysis/runs").json()
    assert {run["analysis_id"] for run in runs} == {
        first["analysis_id"],
        second["analysis_id"],
    }
    assert (
        client.get(
            f"/api/v1/cases/{case_id}/analysis/runs/{first['analysis_id']}"
        ).json()
        == first
    )
    assert client.get(
        f"/api/v1/cases/{case_id}/findings",
        params={"analysis_id": first["analysis_id"]},
    ).json() == first["findings"]


def test_case_scoping_and_missing_analysis_are_explicit(client):
    first_case = create_case(client, "First")["case_id"]
    second_case = create_case(client, "Second")["case_id"]
    event = ingest(
        client,
        first_case,
        b"timestamp,device_id,event_type\n1,d1,telemetry\n",
    ).json()["events"][0]

    assert client.get(f"/api/v1/cases/{second_case}/events").json() == []
    assert client.get(
        f"/api/v1/cases/{second_case}/events/{event['event_id']}"
    ).status_code == 404
    assert client.get(f"/api/v1/cases/{first_case}/analysis").status_code == 404
    assert client.get(
        f"/api/v1/cases/{first_case}/analysis/runs/{uuid4()}"
    ).status_code == 404
    assert client.post(
        "/api/v1/cases/999/evidence",
        params={"filename": "x.csv", "source_type": "simulated"},
        content=b"x",
    ).status_code == 404


def test_openapi_exposes_step8_surface(client):
    paths = client.get("/openapi.json").json()["paths"]
    expected = {
        "/api/v1/cases",
        "/api/v1/cases/{case_id}",
        "/api/v1/cases/{case_id}/evidence",
        "/api/v1/cases/{case_id}/events",
        "/api/v1/cases/{case_id}/alerts",
        "/api/v1/cases/{case_id}/alerts/{alert_id}",
        "/api/v1/cases/{case_id}/incidents",
        "/api/v1/cases/{case_id}/incidents/{incident_id}",
        "/api/v1/cases/{case_id}/timeline",
        "/api/v1/cases/{case_id}/graph",
        "/api/v1/cases/{case_id}/charts",
        "/api/v1/cases/{case_id}/analysis/reanalyze",
    }
    assert expected <= set(paths)
