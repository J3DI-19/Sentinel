from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.evidence.schemas import LiveTelemetryInput, ValidatedLiveTelemetry
from app.evidence.service import LiveTelemetryAcceptanceService


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
    accepted = LiveTelemetryAcceptanceService().accept(telemetry)

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


def test_live_acceptance_rejects_caller_controlled_ingestion_fields():
    telemetry = LiveTelemetryInput.model_validate(valid_payload())

    with pytest.raises(ValidationError):
        ValidatedLiveTelemetry(
            telemetry=telemetry,
            ingested_at=datetime(2000, 1, 1, tzinfo=timezone.utc),
        )
    with pytest.raises(ValidationError):
        ValidatedLiveTelemetry.model_validate(
            {"telemetry": telemetry, "unexpected": "not-in-contract"}
        )


def test_live_acceptance_uses_backend_clock_and_normalizes_to_utc():
    telemetry = LiveTelemetryInput.model_validate(valid_payload())
    backend_time = datetime(
        2026, 8, 6, 10, 30, tzinfo=timezone(timedelta(hours=5, minutes=30))
    )

    accepted = LiveTelemetryAcceptanceService(lambda: backend_time).accept(telemetry)

    assert accepted.ingested_at == datetime(2026, 8, 6, 5, 0, tzinfo=timezone.utc)


def test_live_acceptance_rejects_a_naive_backend_clock():
    telemetry = LiveTelemetryInput.model_validate(valid_payload())

    with pytest.raises(ValueError, match="timezone-aware"):
        LiveTelemetryAcceptanceService(lambda: datetime(2026, 8, 6, 5, 0)).accept(
            telemetry
        )
