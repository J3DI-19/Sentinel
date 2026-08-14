from datetime import timezone

import pytest
from pydantic import ValidationError

from app.evidence.schemas import LiveTelemetryInput, ValidatedLiveTelemetry


def valid_payload():
    return {
        "schema_version": "1.0",
        "case_id": 1,
        "source_id": "arduino-lab-1",
        "device_id": "door-sensor-1",
        "event_type": "telemetry",
        "observed_at": "2026-08-06T10:00:00+05:30",
        "sequence": 42,
        "metrics": {"door_open": True, "battery_voltage": 4.8},
    }


def test_live_contract_normalizes_observed_time_and_records_ingestion_time():
    telemetry = LiveTelemetryInput.model_validate(valid_payload())
    accepted = ValidatedLiveTelemetry(telemetry=telemetry)

    assert telemetry.observed_at.tzinfo == timezone.utc
    assert telemetry.observed_at.isoformat() == "2026-08-06T04:30:00+00:00"
    assert accepted.ingested_at.tzinfo == timezone.utc


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", "2.0"),
        ("source_id", "../../source"),
        ("device_id", "device with spaces"),
        ("event_type", "unknown"),
        ("observed_at", "2026-08-06T10:00:00"),
    ],
)
def test_live_contract_rejects_malformed_identity_type_and_time(field, value):
    payload = valid_payload()
    payload[field] = value

    with pytest.raises(ValidationError):
        LiveTelemetryInput.model_validate(payload)


def test_live_contract_rejects_non_finite_measurements():
    payload = valid_payload()
    payload["metrics"] = {"temperature": float("nan")}

    with pytest.raises(ValidationError):
        LiveTelemetryInput.model_validate(payload)


def test_live_contract_rejects_unknown_fields_and_empty_telemetry_metrics():
    unknown = valid_payload()
    unknown["unexpected"] = "not-in-contract"
    empty_metrics = valid_payload()
    empty_metrics["metrics"] = {}

    with pytest.raises(ValidationError):
        LiveTelemetryInput.model_validate(unknown)
    with pytest.raises(ValidationError):
        LiveTelemetryInput.model_validate(empty_metrics)
