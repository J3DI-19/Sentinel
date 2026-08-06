from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from pathlib import PurePosixPath, PureWindowsPath
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from app.evidence.hashing import sha256_bytes
from app.evidence.profiles import DatasetProfile, get_profile
from app.evidence.schemas import (
    EvidenceMetadata,
    EvidenceSource,
    EvidenceValidationIssue,
    EvidenceValidationReport,
    IssueLevel,
    ValidationStatus,
)

if TYPE_CHECKING:
    from app.db.sqlite import SQLiteRepository


VALIDATOR_VERSION = "1.0"
SUPPORTED_EXTENSIONS = {".csv", ".json"}


class EvidenceValidationService:
    def __init__(
        self,
        repository: SQLiteRepository | None = None,
        *,
        max_file_size_bytes: int = 50 * 1024 * 1024,
        max_issues: int = 100,
    ) -> None:
        if max_file_size_bytes <= 0 or max_issues <= 0:
            raise ValueError("validation limits must be positive")
        self.repository = repository
        self.max_file_size_bytes = max_file_size_bytes
        self.max_issues = max_issues

    def validate(
        self,
        *,
        filename: str,
        content: bytes,
        source_type: EvidenceSource,
        case_id: int | None = None,
        media_type: str | None = None,
    ) -> EvidenceValidationReport:
        profile = get_profile(source_type)
        digest = sha256_bytes(content)
        sanitized_filename, filename_issue = self._validate_filename(filename)
        metadata = EvidenceMetadata(
            evidence_id=uuid4(),
            case_id=case_id,
            original_filename=filename,
            sanitized_filename=sanitized_filename,
            media_type=media_type,
            byte_size=len(content),
            sha256=digest,
            source_type=source_type,
            dataset_profile=profile.name,
            validator_version=VALIDATOR_VERSION,
            received_at=datetime.now(timezone.utc),
        )
        issues: list[EvidenceValidationIssue] = []
        if filename_issue:
            issues.append(filename_issue)
        extension = PureWindowsPath(sanitized_filename).suffix.lower()
        if extension not in SUPPORTED_EXTENSIONS:
            issues.append(self._issue("UNSUPPORTED_FILE_TYPE", "Only CSV and JSON evidence files are supported"))
        if not content:
            issues.append(self._issue("EMPTY_FILE", "Evidence file is empty"))
        if len(content) > self.max_file_size_bytes:
            issues.append(
                self._issue(
                    "FILE_TOO_LARGE",
                    f"Evidence file exceeds the {self.max_file_size_bytes}-byte limit",
                )
            )

        records: list[dict[str, Any]] = []
        if not self._has_errors(issues):
            records, parse_issues = self._parse(extension, content)
            issues.extend(parse_issues)

        accepted = 0
        rejected = 0
        if records and not self._has_file_errors(issues):
            column_issues = self._validate_columns(records, profile)
            issues.extend(column_issues)
            if column_issues:
                rejected = len(records)
            else:
                accepted, rejected, record_issues = self._validate_records(records, profile)
                issues.extend(record_issues)

        if self.repository is not None and case_id is not None:
            duplicate = self.repository.find_evidence_by_hash(case_id, digest)
            if duplicate is not None:
                issues.append(
                    self._issue(
                        "DUPLICATE_EVIDENCE",
                        f"The same evidence bytes were already registered as {duplicate}",
                        level=IssueLevel.WARNING,
                    )
                )

        issues = issues[: self.max_issues]
        status = self._status(issues, accepted, rejected)
        report = EvidenceValidationReport(
            metadata=metadata,
            status=status,
            total_records=len(records),
            accepted_records=accepted,
            rejected_records=rejected,
            issues=issues,
        )
        if self.repository is not None:
            self.repository.store_evidence_validation(report)
        return report

    def _parse(self, extension: str, content: bytes) -> tuple[list[dict[str, Any]], list[EvidenceValidationIssue]]:
        try:
            text = content.decode("utf-8-sig", errors="strict")
        except UnicodeDecodeError:
            return [], [self._issue("INVALID_ENCODING", "Evidence must use UTF-8 encoding")]
        if extension == ".csv":
            return self._parse_csv(text)
        return self._parse_json(text)

    def _parse_csv(self, text: str) -> tuple[list[dict[str, Any]], list[EvidenceValidationIssue]]:
        try:
            reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
            if reader.fieldnames is None:
                return [], [self._issue("MISSING_HEADER", "CSV evidence must include a header row")]
            fieldnames = [name.strip() if name else "" for name in reader.fieldnames]
            normalized = [name.casefold() for name in fieldnames]
            if any(not name for name in fieldnames):
                return [], [self._issue("EMPTY_COLUMN_NAME", "CSV column names cannot be empty")]
            if len(normalized) != len(set(normalized)):
                return [], [self._issue("DUPLICATE_COLUMN", "CSV column names must be unique")]
            records = []
            for raw in reader:
                if None in raw:
                    return [], [self._issue("ROW_SHAPE_MISMATCH", "A CSV row has more values than the header")]
                if any(value is None for value in raw.values()):
                    return [], [self._issue("ROW_SHAPE_MISMATCH", "A CSV row has fewer values than the header")]
                records.append({key.strip(): value for key, value in raw.items()})
            if not records:
                return [], [self._issue("NO_RECORDS", "Evidence contains no data records")]
            return records, []
        except csv.Error as exc:
            return [], [self._issue("MALFORMED_CSV", f"CSV parsing failed: {exc}")]

    def _parse_json(self, text: str) -> tuple[list[dict[str, Any]], list[EvidenceValidationIssue]]:
        try:
            payload = json.loads(text, parse_constant=self._reject_json_constant)
        except json.JSONDecodeError as exc:
            return [], [self._issue("MALFORMED_JSON", f"JSON parsing failed at line {exc.lineno}, column {exc.colno}")]
        except ValueError as exc:
            return [], [self._issue("NON_FINITE_JSON_NUMBER", str(exc))]
        if isinstance(payload, dict) and "records" in payload:
            payload = payload["records"]
        if not isinstance(payload, list):
            return [], [self._issue("INVALID_JSON_SHAPE", "JSON evidence must be a list or an object containing a records list")]
        if not payload:
            return [], [self._issue("NO_RECORDS", "Evidence contains no data records")]
        if not all(isinstance(record, dict) for record in payload):
            return [], [self._issue("INVALID_JSON_RECORD", "Every JSON evidence record must be an object")]
        return payload, []

    @staticmethod
    def _reject_json_constant(value: str) -> None:
        raise ValueError(f"JSON contains unsupported numeric constant {value!r}")

    def _validate_columns(
        self, records: list[dict[str, Any]], profile: DatasetProfile
    ) -> list[EvidenceValidationIssue]:
        columns = {str(column).strip().casefold() for record in records for column in record}
        missing = [column for column in profile.required_columns if column.casefold() not in columns]
        return [
            self._issue("MISSING_REQUIRED_COLUMN", f"Required column {column!r} is missing", field=column)
            for column in missing
        ]

    def _validate_records(
        self, records: list[dict[str, Any]], profile: DatasetProfile
    ) -> tuple[int, int, list[EvidenceValidationIssue]]:
        accepted = 0
        rejected = 0
        issues: list[EvidenceValidationIssue] = []
        for row_number, record in enumerate(records, start=1):
            normalized_record = {str(key).strip().casefold(): value for key, value in record.items()}
            row_valid = True
            for field, (code, validator) in profile.validators.items():
                raw_value = normalized_record.get(field.casefold())
                value = "" if raw_value is None else str(raw_value)
                if not validator(value):
                    row_valid = False
                    if len(issues) < self.max_issues:
                        issues.append(
                            self._issue(
                                code,
                                f"Invalid value for {field!r}",
                                row_number=row_number,
                                field=field,
                                rejected_value=self._preview(value),
                            )
                        )
            if row_valid:
                accepted += 1
            else:
                rejected += 1
        return accepted, rejected, issues

    @staticmethod
    def _validate_filename(filename: str) -> tuple[str, EvidenceValidationIssue | None]:
        sanitized = PureWindowsPath(filename).name
        posix_name = PurePosixPath(filename).name
        if posix_name != filename or sanitized != filename or filename in {"", ".", ".."} or "\x00" in filename:
            safe_name = sanitized if sanitized not in {"", ".", ".."} else "invalid"
            return safe_name, EvidenceValidationService._issue(
                "UNSAFE_FILENAME",
                "Filename must not contain paths, null bytes, or traversal segments",
            )
        return sanitized, None

    @staticmethod
    def _preview(value: str) -> str:
        return value if len(value) <= 256 else f"{value[:253]}..."

    @staticmethod
    def _issue(
        code: str,
        message: str,
        *,
        level: IssueLevel = IssueLevel.ERROR,
        row_number: int | None = None,
        field: str | None = None,
        rejected_value: str | None = None,
    ) -> EvidenceValidationIssue:
        return EvidenceValidationIssue(
            level=level,
            code=code,
            message=message,
            row_number=row_number,
            field=field,
            rejected_value=rejected_value,
        )

    @staticmethod
    def _has_errors(issues: list[EvidenceValidationIssue]) -> bool:
        return any(issue.level == IssueLevel.ERROR for issue in issues)

    @staticmethod
    def _has_file_errors(issues: list[EvidenceValidationIssue]) -> bool:
        return any(issue.level == IssueLevel.ERROR and issue.row_number is None for issue in issues)

    @staticmethod
    def _status(
        issues: list[EvidenceValidationIssue], accepted: int, rejected: int
    ) -> ValidationStatus:
        if accepted == 0 or any(issue.level == IssueLevel.ERROR and issue.row_number is None for issue in issues):
            return ValidationStatus.REJECTED
        if rejected or issues:
            return ValidationStatus.ACCEPTED_WITH_WARNINGS
        return ValidationStatus.ACCEPTED
