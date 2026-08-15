from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.evidence.authorization import DEFAULT_VALIDATION_AUTHORITY
from app.evidence.hashing import sha256_record
from app.evidence.profiles import get_profile
from app.evidence.schemas import (
    EvidenceMetadata,
    EvidenceSource,
    LiveTelemetryInput,
    ValidatedBatchRecord,
)
from app.evidence.service import EvidenceValidationService, LiveTelemetryAcceptanceService
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
FIXTURES = Path(__file__).parent / "fixtures"


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
        dataset_profile=get_profile(source).name,
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
    record_hash = raw_record_hash or sha256_record(record)
    return ValidatedBatchRecord(
        evidence_id=evidence_id,
        source_type=source,
        dataset_profile=get_profile(source).name,
        validator_version="1.0",
        row_number=row_number,
        record=record,
        raw_record_hash=record_hash,
        validation_seal=DEFAULT_VALIDATION_AUTHORITY.seal(
            evidence_id=evidence_id,
            source_type=source,
            dataset_profile=get_profile(source).name,
            validator_version="1.0",
            source_hash=SOURCE_HASH,
            row_number=row_number,
            raw_record_hash=record_hash,
        ),
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


def test_casas_milan_adapter_maps_sensor_state_identity_activity_and_provenance():
    record = {
        "timestamp": "2009-10-16T21:06:34.000010",
        "sensor_id": "D003",
        "sensor_message": "OPEN",
        "activity": "Cook begin",
    }

    result = NormalizationService().normalize_batch_record(
        metadata=metadata(EvidenceSource.CASAS_SMART_HOME),
        validated_record=validated_record(EvidenceSource.CASAS_SMART_HOME, 1, record),
    )

    assert result.status == NormalizationStatus.NORMALIZED
    event = result.event
    assert event.observed_at == datetime(
        2009, 10, 16, 21, 6, 34, 10, tzinfo=timezone.utc
    )
    assert event.event_type == "device_state"
    assert event.device.id == "D003"
    assert event.device.device_type == "door_sensor"
    assert event.target == event.device
    assert event.attributes == {
        "value": "OPEN",
        "activity": "Cook begin",
    }
    assert event.provenance.source_type.value == "casas_smart_home"
    assert "ASSUMED_UTC" in warning_codes(event)


def test_ton_iot_fridge_adapter_maps_benign_and_anomalous_telemetry():
    benign = {
        "date": "31-Mar-19",
        "time": "12:36:52",
        "fridge_temperature": "13.1",
        "temp_condition": "low",
        "label": "0",
        "type": "normal",
    }
    anomalous = {
        **benign,
        "time": "12:37:52",
        "fridge_temperature": "21.4",
        "temp_condition": "high",
        "label": "1",
        "type": "backdoor",
    }

    events = [
        NormalizationService().normalize_batch_record(
            metadata=metadata(EvidenceSource.TON_IOT_TELEMETRY),
            validated_record=validated_record(
                EvidenceSource.TON_IOT_TELEMETRY, index, record
            ),
        ).event
        for index, record in enumerate((benign, anomalous), start=1)
    ]

    assert all(event is not None for event in events)
    assert events[0].observed_at == datetime(2019, 3, 31, 12, 36, 52, tzinfo=timezone.utc)
    assert events[0].device.id == "ton-iot-fridge"
    assert events[0].device.device_type == "smart_refrigerator"
    assert events[0].attributes["fridge_temperature"] == 13.1
    assert events[0].source_label == "0"
    assert events[1].attributes == {
        "fridge_temperature": 21.4,
        "temperature_condition": "high",
        "attack_type": "backdoor",
    }
    assert events[1].source_label == "1"
    assert events[1].source_event_type == "backdoor"
    assert "ASSUMED_UTC" in warning_codes(events[1])


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
    accepted = LiveTelemetryAcceptanceService(lambda: INGESTED_AT).accept(telemetry)

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


@pytest.mark.parametrize(
    ("fixture_name", "source"),
    [
        ("casas_milan_valid.csv", EvidenceSource.CASAS_SMART_HOME),
        (
            "ton_iot_fridge_telemetry_valid.csv",
            EvidenceSource.TON_IOT_TELEMETRY,
        ),
    ],
)
def test_primary_dataset_fixtures_cross_the_step3_step4_boundary(
    fixture_name, source
):
    fixture = FIXTURES / fixture_name
    outcome = EvidenceValidationService().validate_with_records(
        filename=fixture.name,
        content=fixture.read_bytes(),
        source_type=source,
        case_id=1,
    )

    assert outcome.report.status == "accepted"
    result = NormalizationService().normalize_batch_record(
        metadata=outcome.report.metadata,
        validated_record=outcome.accepted_records[0],
    )

    assert result.status == NormalizationStatus.NORMALIZED
    assert result.event.provenance.source_type.value == source.value


def test_step4_rejects_a_self_hashed_row_without_step3_authorization():
    record = {"timestamp": "1", "device_id": "d1", "event_type": "telemetry"}
    forged = validated_record(EvidenceSource.SIMULATED, 1, record).model_copy(
        update={"validation_seal": "0" * 64}
    )

    result = NormalizationService().normalize_batch_record(
        metadata=metadata(EvidenceSource.SIMULATED),
        validated_record=forged,
    )

    assert result.status == NormalizationStatus.REJECTED
    assert result.issues[0].code == "VALIDATION_SEAL_INVALID"
