from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.evidence.hashing import sha256_record
from app.evidence.schemas import (
    EvidenceMetadata,
    EvidenceSource,
    LiveTelemetryInput,
    ValidatedBatchRecord,
    ValidatedLiveTelemetry,
)
from app.evidence.service import EvidenceValidationService
from app.normalization.schemas import (
    CanonicalEvent,
    EventOrigin,
    NormalizationStatus,
)
from app.normalization.service import NormalizationService


EVIDENCE_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
LIVE_EVIDENCE_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
SOURCE_HASH = "1" * 64
INGESTED_AT = datetime(2026, 8, 6, 5, 0, tzinfo=timezone.utc)


def metadata(source: EvidenceSource, *, case_id: int | None = 1) -> EvidenceMetadata:
    return EvidenceMetadata(
        evidence_id=EVIDENCE_ID,
        case_id=case_id,
        original_filename="evidence.csv",
        sanitized_filename="evidence.csv",
        media_type="text/csv",
        byte_size=100,
        sha256=SOURCE_HASH,
        source_type=source,
        dataset_profile=f"{source.value}@1.0",
        validator_version="1.0",
        received_at=INGESTED_AT,
    )


def warning_codes(event: CanonicalEvent) -> set[str]:
    return {warning.code for warning in event.normalization_warnings}


def validated_record(
    source: EvidenceSource,
    row_number: int,
    record: dict,
    *,
    evidence_id: UUID = EVIDENCE_ID,
    raw_record_hash: str | None = None,
) -> ValidatedBatchRecord:
    return ValidatedBatchRecord(
        evidence_id=evidence_id,
        source_type=source,
        dataset_profile=f"{source.value}@1.0",
        validator_version="1.0",
        row_number=row_number,
        record=record,
        raw_record_hash=raw_record_hash or sha256_record(record),
    )


def test_simulated_adapter_standardizes_fields_and_is_reproducible():
    record = {
        "timestamp": "2026-08-06 10:30:00",
        "device_id": "camera-1",
        "device_type": "smart_camera",
        "event_type": "Authentication Failure",
        "src_ip": "203.0.113.8",
        "dst_ip": "192.0.2.20",
        "dst_port": "443",
        "proto": "TCP",
        "outcome": "Denied",
        "attempts": 4,
    }
    original = record.copy()
    service = NormalizationService()

    first = service.normalize_batch_record(
        metadata=metadata(EvidenceSource.SIMULATED),
        validated_record=validated_record(EvidenceSource.SIMULATED, 7, record),
    )
    second = service.normalize_batch_record(
        metadata=metadata(EvidenceSource.SIMULATED),
        validated_record=validated_record(EvidenceSource.SIMULATED, 7, record),
    )

    assert first.status == NormalizationStatus.NORMALIZED
    event = first.event
    assert event is not None
    assert event.schema_version == "1.0"
    assert event.event_id == second.event.event_id
    assert event.observed_at == datetime(2026, 8, 6, 10, 30, tzinfo=timezone.utc)
    assert event.ingested_at == INGESTED_AT
    assert event.event_type == "authentication_failure"
    assert event.source_event_type == "Authentication Failure"
    assert event.device.id == "camera-1"
    assert str(event.actor.ip) == "203.0.113.8"
    assert event.network.destination_port == 443
    assert event.network.protocol == "tcp"
    assert event.outcome == "denied"
    assert event.attributes == {"attempts": 4}
    assert event.provenance.source_record_reference == "row:7"
    assert event.provenance.evidence_id == EVIDENCE_ID
    assert "ASSUMED_UTC" in warning_codes(event)
    assert record == original


def test_ton_iot_adapter_preserves_label_and_network_without_inventing_device():
    record = {
        "ts": "1598880000",
        "src_ip": "203.0.113.8",
        "src_port": "50123",
        "dst_ip": "192.0.2.20",
        "dst_port": "554",
        "proto": "tcp",
        "src_bytes": "120",
        "dst_bytes": "48",
        "src_pkts": "3",
        "dst_pkts": "2",
        "label": "1",
        "type": "scanning",
    }
    result = NormalizationService().normalize_batch_record(
        metadata=metadata(EvidenceSource.TON_IOT_NETWORK),
        validated_record=validated_record(EvidenceSource.TON_IOT_NETWORK, 18_224, record),
    )

    assert result.status == NormalizationStatus.NORMALIZED
    event = result.event
    assert event.event_type == "network_flow"
    assert event.source_event_type == "scanning"
    assert event.source_label == "1"
    assert event.device is None
    assert event.target.id == "ip:192.0.2.20"
    assert event.actor.id == "ip:203.0.113.8"
    assert event.network.bytes_sent == 120
    assert event.network.packets_received == 2
    assert event.provenance.source_record_reference == "row:18224"
    assert "DEVICE_ID_UNAVAILABLE" in warning_codes(event)


def test_ciciot_adapter_does_not_invent_missing_time_or_device_identity():
    record = {
        "flow_duration": "1.25",
        "Protocol Type": "6",
        "Header_Length": "40",
        "Duration": "64",
        "Rate": "8.0",
        "label": "BenignTraffic",
    }
    result = NormalizationService().normalize_batch_record(
        metadata=metadata(EvidenceSource.CICIOT2023_NETWORK),
        validated_record=validated_record(EvidenceSource.CICIOT2023_NETWORK, 7712, record),
    )

    assert result.status == NormalizationStatus.NORMALIZED
    event = result.event
    assert event.observed_at is None
    assert event.device is None
    assert event.event_type == "network_flow"
    assert event.source_label == "BenignTraffic"
    assert event.network.protocol == "6"
    assert event.attributes == {
        "flow_duration": 1.25,
        "header_length": 40,
        "duration": 64,
        "rate": 8.0,
    }
    assert {"OBSERVED_TIME_UNAVAILABLE", "DEVICE_ID_UNAVAILABLE"} <= warning_codes(event)


def test_live_adapter_converges_on_canonical_schema_and_preserves_provenance():
    telemetry = LiveTelemetryInput.model_validate(
        {
            "schema_version": "1.0",
            "case_id": 1,
            "source_id": "arduino-lab-1",
            "device_id": "door-sensor-1",
            "event_type": "telemetry",
            "observed_at": "2026-08-06T10:30:00+05:30",
            "sequence": 42,
            "metrics": {"door_open": True, "battery_voltage": 4.8},
        }
    )
    accepted = ValidatedLiveTelemetry(telemetry=telemetry, ingested_at=INGESTED_AT)

    result = NormalizationService().normalize_live_telemetry(
        accepted=accepted,
        evidence_id=LIVE_EVIDENCE_ID,
        source_hash="2" * 64,
        source_name="arduino-lab-collector",
    )

    assert result.status == NormalizationStatus.NORMALIZED
    event = result.event
    assert isinstance(event, CanonicalEvent)
    assert event.observed_at == datetime(2026, 8, 6, 5, 0, tzinfo=timezone.utc)
    assert event.ingested_at == INGESTED_AT
    assert event.device.id == "door-sensor-1"
    assert event.attributes == {
        "door_open": True,
        "battery_voltage": 4.8,
        "sequence": 42,
    }
    assert event.provenance.origin == EventOrigin.LIVE
    assert event.provenance.source_id == "arduino-lab-1"
    assert event.provenance.source_record_reference == "sequence:42"
    assert event.provenance.evidence_id == LIVE_EVIDENCE_ID
    assert event.action is None

    batch_record = {
        "timestamp": "2026-08-06T05:00:00Z",
        "device_id": "door-sensor-1",
        "event_type": "telemetry",
    }
    batch = NormalizationService().normalize_batch_record(
        metadata=metadata(EvidenceSource.SIMULATED),
        validated_record=validated_record(EvidenceSource.SIMULATED, 1, batch_record),
    ).event
    assert set(event.model_dump()) == set(batch.model_dump()) == set(CanonicalEvent.model_fields)


def test_invalid_direct_inputs_are_rejected_with_explicit_reasons():
    service = NormalizationService()
    valid_record = {"timestamp": "1", "device_id": "d1", "event_type": "telemetry"}
    missing_case = service.normalize_batch_record(
        metadata=metadata(EvidenceSource.SIMULATED, case_id=None),
        validated_record=validated_record(EvidenceSource.SIMULATED, 1, valid_record),
    )
    mismatched_evidence = service.normalize_batch_record(
        metadata=metadata(EvidenceSource.SIMULATED),
        validated_record=validated_record(
            EvidenceSource.SIMULATED, 1, valid_record, evidence_id=LIVE_EVIDENCE_ID
        ),
    )
    tampered_record = service.normalize_batch_record(
        metadata=metadata(EvidenceSource.SIMULATED),
        validated_record=validated_record(
            EvidenceSource.SIMULATED, 1, valid_record, raw_record_hash="0" * 64
        ),
    )
    missing_timestamp = {"device_id": "d1", "event_type": "telemetry"}
    invalid_record = service.normalize_batch_record(
        metadata=metadata(EvidenceSource.SIMULATED),
        validated_record=validated_record(EvidenceSource.SIMULATED, 1, missing_timestamp),
    )
    oversized = {"timestamp": "1", "device_id": "x" * 300, "event_type": "telemetry"}
    oversized_identifier = service.normalize_batch_record(
        metadata=metadata(EvidenceSource.SIMULATED),
        validated_record=validated_record(EvidenceSource.SIMULATED, 1, oversized),
    )

    assert missing_case.status == NormalizationStatus.REJECTED
    assert missing_case.issues[0].code == "CASE_ID_REQUIRED"
    assert mismatched_evidence.issues[0].code == "VALIDATED_RECORD_MISMATCH"
    assert tampered_record.issues[0].code == "VALIDATED_RECORD_HASH_MISMATCH"
    assert invalid_record.issues[0].code == "INVALID_TIMESTAMP"
    assert oversized_identifier.status == NormalizationStatus.REJECTED
    assert oversized_identifier.issues[0].code == "CANONICAL_SCHEMA_REJECTED"


def test_flat_csv_attributes_are_conservatively_typed():
    record = {
        "timestamp": "1",
        "device_id": "d1",
        "event_type": "telemetry",
        "attempts": "14",
        "temperature": "-2.5",
        "enabled": "true",
        "padded_identifier": "001",
    }
    result = NormalizationService().normalize_batch_record(
        metadata=metadata(EvidenceSource.SIMULATED),
        validated_record=validated_record(EvidenceSource.SIMULATED, 1, record),
    )

    assert result.event.attributes == {
        "attempts": 14,
        "temperature": -2.5,
        "enabled": True,
        "padded_identifier": "001",
    }


def test_canonical_schema_rejects_derived_risk_fields():
    record = {"timestamp": "1", "event_type": "status_change"}
    result = NormalizationService().normalize_batch_record(
        metadata=metadata(EvidenceSource.GENERIC),
        validated_record=validated_record(EvidenceSource.GENERIC, 1, record),
    )
    payload = result.event.model_dump(mode="json")
    payload["risk"] = 99

    with pytest.raises(ValidationError):
        CanonicalEvent.model_validate(payload)


def test_rejects_ambiguous_normalized_source_fields():
    record = {
        "timestamp": "1",
        "device_id": "d1",
        "event_type": "network",
        "src-ip": "203.0.113.1",
        "src_ip": "203.0.113.2",
    }
    result = NormalizationService().normalize_batch_record(
        metadata=metadata(EvidenceSource.SIMULATED),
        validated_record=validated_record(EvidenceSource.SIMULATED, 1, record),
    )

    assert result.status == NormalizationStatus.REJECTED
    assert result.issues[0].code == "AMBIGUOUS_SOURCE_FIELDS"


@pytest.mark.parametrize(
    ("source", "record"),
    [
        (
            EvidenceSource.TON_IOT_NETWORK,
            {"ts": "1", "src_ip": "203.0.113.1", "dst_ip": "192.0.2.1"},
        ),
        (
            EvidenceSource.CICIOT2023_NETWORK,
            {"flow_duration": "1", "Protocol Type": "6"},
        ),
    ],
)
def test_dataset_adapters_defensively_require_profile_fields(source, record):
    result = NormalizationService().normalize_batch_record(
        metadata=metadata(source),
        validated_record=validated_record(source, 1, record),
    )

    assert result.status == NormalizationStatus.REJECTED
    assert result.issues[0].code == "MISSING_REQUIRED_FIELD"


def test_rejects_empty_generic_record():
    result = NormalizationService().normalize_batch_record(
        metadata=metadata(EvidenceSource.GENERIC),
        validated_record=validated_record(EvidenceSource.GENERIC, 1, {}),
    )

    assert result.status == NormalizationStatus.REJECTED
    assert result.issues[0].code == "EMPTY_CANONICAL_RECORD"


def test_step3_accepted_row_is_the_step4_batch_input():
    content = (
        b"timestamp,device_id,event_type,value\n"
        b"2026-08-06T10:00:00Z,sensor-1,telemetry,21.4\n"
    )
    outcome = EvidenceValidationService().validate_with_records(
        filename="evidence.csv",
        content=content,
        source_type=EvidenceSource.SIMULATED,
        case_id=1,
    )

    assert len(outcome.accepted_records) == 1
    result = NormalizationService().normalize_batch_record(
        metadata=outcome.report.metadata,
        validated_record=outcome.accepted_records[0],
    )
    assert result.status == NormalizationStatus.NORMALIZED
    assert result.event.provenance.raw_record_hash == outcome.accepted_records[0].raw_record_hash
