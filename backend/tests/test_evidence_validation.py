from __future__ import annotations

from pathlib import Path

import pytest

from app.db.sqlite import SQLiteRepository
from app.evidence.hashing import sha256_bytes, sha256_record
from app.evidence.schemas import EvidenceSource, IssueLevel, ValidationStatus
from app.evidence.service import EvidenceValidationService


def issue_codes(report):
    return {issue.code for issue in report.issues}


FIXTURES = Path(__file__).parent / "fixtures"


def test_accepts_valid_simulated_csv_and_hashes_original_bytes():
    content = (
        b"timestamp,device_id,event_type,value\n"
        b"2026-08-06T10:00:00Z,sensor-1,telemetry,21.4\n"
    )

    report = EvidenceValidationService().validate(
        filename="evidence.csv",
        content=content,
        source_type=EvidenceSource.SIMULATED,
        media_type="text/csv",
    )

    assert report.status == ValidationStatus.ACCEPTED
    assert report.total_records == 1
    assert report.accepted_records == 1
    assert report.rejected_records == 0
    assert report.metadata.sha256 == sha256_bytes(content)
    assert report.metadata.dataset_profile == "simulated@1.0"


def test_rejects_unsafe_filename_before_parsing():
    report = EvidenceValidationService().validate(
        filename="../evidence.csv",
        content=b"timestamp,device_id,event_type\n1,d1,telemetry\n",
        source_type=EvidenceSource.SIMULATED,
    )

    assert report.status == ValidationStatus.REJECTED
    assert "UNSAFE_FILENAME" in issue_codes(report)
    assert report.total_records == 0


def test_rejects_unsupported_empty_and_oversized_files():
    empty = EvidenceValidationService().validate(
        filename="evidence.exe",
        content=b"",
        source_type=EvidenceSource.GENERIC,
    )
    oversized = EvidenceValidationService(max_file_size_bytes=3).validate(
        filename="evidence.json",
        content=b"[{}]",
        source_type=EvidenceSource.GENERIC,
    )

    assert empty.status == ValidationStatus.REJECTED
    assert issue_codes(empty) == {"UNSUPPORTED_FILE_TYPE", "EMPTY_FILE"}
    assert oversized.status == ValidationStatus.REJECTED
    assert "FILE_TOO_LARGE" in issue_codes(oversized)


def test_reports_missing_required_columns():
    report = EvidenceValidationService().validate(
        filename="ton.csv",
        content=b"ts,src_ip,label\n1,10.0.0.1,0\n",
        source_type=EvidenceSource.TON_IOT_NETWORK,
    )

    assert report.status == ValidationStatus.REJECTED
    assert report.total_records == 1
    assert report.accepted_records == 0
    assert report.rejected_records == 1
    issue = next(issue for issue in report.issues if issue.code == "MISSING_REQUIRED_COLUMN")
    assert issue.field == "dst_ip"


def test_accepts_valid_rows_and_documents_invalid_rows():
    content = (
        b"timestamp,device_id,event_type\n"
        b"2026-08-06T10:00:00+05:30,sensor-1,telemetry\n"
        b"not-a-time,sensor-2,telemetry\n"
        b"2026-08-06T10:01:00Z,,device_state\n"
    )

    report = EvidenceValidationService().validate(
        filename="mixed.csv",
        content=content,
        source_type=EvidenceSource.SIMULATED,
    )

    assert report.status == ValidationStatus.ACCEPTED_WITH_WARNINGS
    assert report.total_records == 3
    assert report.accepted_records == 1
    assert report.rejected_records == 2
    assert {(issue.row_number, issue.field, issue.code) for issue in report.issues} == {
        (2, "timestamp", "INVALID_TIMESTAMP"),
        (3, "device_id", "MISSING_VALUE"),
    }


def test_validation_outcome_hands_off_only_accepted_rows_with_hashes():
    content = (
        b"timestamp,device_id,event_type\n"
        b"2026-08-06T10:00:00Z,sensor-1,telemetry\n"
        b"not-a-time,sensor-2,telemetry\n"
    )

    outcome = EvidenceValidationService().validate_with_records(
        filename="mixed.csv",
        content=content,
        source_type=EvidenceSource.SIMULATED,
        case_id=1,
    )

    assert outcome.report.accepted_records == 1
    assert outcome.report.rejected_records == 1
    assert len(outcome.accepted_records) == 1
    accepted = outcome.accepted_records[0]
    assert accepted.evidence_id == outcome.report.metadata.evidence_id
    assert accepted.row_number == 1
    assert accepted.raw_record_hash == sha256_record(accepted.record)


def test_validates_json_records_and_rejects_malformed_shape():
    valid = EvidenceValidationService().validate(
        filename="records.json",
        content=(
            b'{"records":[{"timestamp":"1","device_id":"d1",'
            b'"event_type":"heartbeat"}]}'
        ),
        source_type=EvidenceSource.SIMULATED,
    )
    invalid = EvidenceValidationService().validate(
        filename="records.json",
        content=b'{"timestamp":"1"}',
        source_type=EvidenceSource.SIMULATED,
    )

    assert valid.status == ValidationStatus.ACCEPTED
    assert invalid.status == ValidationStatus.REJECTED
    assert "INVALID_JSON_SHAPE" in issue_codes(invalid)


def test_rejects_short_csv_rows_nonstandard_json_numbers_and_infinity():
    short_row = EvidenceValidationService().validate(
        filename="short.csv",
        content=b"first,second\nvalue\n",
        source_type=EvidenceSource.GENERIC,
    )
    nonstandard_json = EvidenceValidationService().validate(
        filename="number.json",
        content=b'[{"value": NaN}]',
        source_type=EvidenceSource.GENERIC,
    )
    infinite_timestamp = EvidenceValidationService().validate(
        filename="timestamp.csv",
        content=b"timestamp,device_id,event_type\nInfinity,d1,telemetry\n",
        source_type=EvidenceSource.SIMULATED,
    )

    assert short_row.status == ValidationStatus.REJECTED
    assert "ROW_SHAPE_MISMATCH" in issue_codes(short_row)
    assert nonstandard_json.status == ValidationStatus.REJECTED
    assert "NON_FINITE_JSON_NUMBER" in issue_codes(nonstandard_json)
    assert infinite_timestamp.status == ValidationStatus.REJECTED
    assert "INVALID_TIMESTAMP" in issue_codes(infinite_timestamp)


@pytest.mark.parametrize(
    ("fixture_name", "source_type"),
    [
        ("simulated_valid.csv", EvidenceSource.SIMULATED),
        ("casas_milan_valid.csv", EvidenceSource.CASAS_SMART_HOME),
        (
            "ton_iot_fridge_telemetry_valid.csv",
            EvidenceSource.TON_IOT_FRIDGE_TELEMETRY,
        ),
        ("ton_iot_network_valid.csv", EvidenceSource.TON_IOT_NETWORK),
        ("ciciot2023_network_valid.csv", EvidenceSource.CICIOT2023_NETWORK),
    ],
)
def test_versioned_profile_contract_fixtures(fixture_name, source_type):
    fixture = FIXTURES / fixture_name

    report = EvidenceValidationService().validate(
        filename=fixture.name,
        content=fixture.read_bytes(),
        source_type=source_type,
    )

    assert report.status == ValidationStatus.ACCEPTED
    assert report.total_records == 1


def test_casas_csv_profile_preserves_activity_and_rejects_invalid_rows():
    content = (
        b"timestamp,sensor_id,sensor_message,activity\n"
        b"2009-10-16T21:06:34.000010,D003,OPEN,Cook begin\n"
        b"not-a-time,M017,OFF,\n"
        b"2009-10-16T21:07:00.000010,,ON,\n"
    )

    outcome = EvidenceValidationService().validate_with_records(
        filename="milan.csv",
        content=content,
        source_type=EvidenceSource.CASAS_SMART_HOME,
        case_id=1,
    )

    assert outcome.report.status == ValidationStatus.ACCEPTED_WITH_WARNINGS
    assert outcome.report.total_records == 3
    assert outcome.report.accepted_records == 1
    assert outcome.report.rejected_records == 2
    assert outcome.accepted_records[0].record["activity"] == "Cook begin"
    assert {"INVALID_TIMESTAMP", "MISSING_SENSOR_ID"} <= issue_codes(outcome.report)


def test_ton_iot_fridge_profile_rejects_bad_time_label_and_missing_state():
    content = (
        b"date,time,fridge_temperature,temp_condition,label,type\n"
        b"31-Mar-19,not-time,13.1,low,0,normal\n"
        b"31-Mar-19,12:36:52,13.1,,2,backdoor\n"
    )

    report = EvidenceValidationService().validate(
        filename="Train_Test_IoT_Fridge.csv",
        content=content,
        source_type=EvidenceSource.TON_IOT_FRIDGE_TELEMETRY,
    )

    assert report.status == ValidationStatus.REJECTED
    assert report.rejected_records == 2
    assert {"INVALID_TIME", "MISSING_DEVICE_STATE", "INVALID_BINARY_LABEL"} <= issue_codes(
        report
    )


@pytest.mark.parametrize(
    "source_type", [EvidenceSource.GENERIC, EvidenceSource.CASAS_SMART_HOME]
)
def test_txt_is_rejected_for_all_profiles(source_type):
    report = EvidenceValidationService().validate(
        filename="arbitrary.txt",
        content=b"untrusted text",
        source_type=source_type,
    )

    assert report.status == ValidationStatus.REJECTED
    assert "UNSUPPORTED_FILE_TYPE" in issue_codes(report)


def test_persists_metadata_issues_and_flags_same_case_duplicate(tmp_path):
    repository = SQLiteRepository(f"sqlite:///{tmp_path / 'evidence.db'}")
    repository.initialize()
    repository.connection.execute("INSERT INTO cases (name) VALUES (?)", ("Case 1",))
    repository.connection.commit()
    service = EvidenceValidationService(repository)
    content = b"timestamp,device_id,event_type\n1,d1,telemetry\n"

    first = service.validate(
        filename="first.csv",
        content=content,
        source_type=EvidenceSource.SIMULATED,
        case_id=1,
    )
    second = service.validate(
        filename="second.csv",
        content=content,
        source_type=EvidenceSource.SIMULATED,
        case_id=1,
    )

    stored = repository.connection.execute(
        "SELECT COUNT(*) AS count FROM evidence_metadata"
    ).fetchone()
    stored_issue = repository.connection.execute(
        "SELECT level, error_code FROM evidence_validation_issues"
    ).fetchone()
    stored_metadata = repository.connection.execute(
        "SELECT adapter_version, dataset_profile FROM evidence_metadata ORDER BY id LIMIT 1"
    ).fetchone()
    assert first.status == ValidationStatus.ACCEPTED
    assert second.status == ValidationStatus.ACCEPTED_WITH_WARNINGS
    assert stored["count"] == 2
    assert dict(stored_issue) == {
        "level": IssueLevel.WARNING.value,
        "error_code": "DUPLICATE_EVIDENCE",
    }
    assert dict(stored_metadata) == {
        "adapter_version": None,
        "dataset_profile": "simulated@1.0",
    }
    repository.close()
