from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EvidenceSource(str, Enum):
    TON_IOT_NETWORK = "ton_iot_network"
    CICIOT2023_NETWORK = "ciciot2023_network"
    SIMULATED = "simulated"
    GENERIC = "generic"


class ValidationStatus(str, Enum):
    ACCEPTED = "accepted"
    ACCEPTED_WITH_WARNINGS = "accepted_with_warnings"
    REJECTED = "rejected"


class IssueLevel(str, Enum):
    ERROR = "error"
    WARNING = "warning"


class EvidenceValidationIssue(BaseModel):
    level: IssueLevel = IssueLevel.ERROR
    code: str
    message: str
    row_number: int | None = Field(default=None, ge=1)
    field: str | None = None
    rejected_value: str | None = Field(default=None, max_length=256)


class EvidenceMetadata(BaseModel):
    evidence_id: UUID
    case_id: int | None = Field(default=None, ge=1)
    original_filename: str
    sanitized_filename: str
    media_type: str | None = None
    byte_size: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_type: EvidenceSource
    dataset_profile: str
    validator_version: str
    received_at: datetime


class EvidenceValidationReport(BaseModel):
    metadata: EvidenceMetadata
    status: ValidationStatus
    total_records: int = Field(ge=0)
    accepted_records: int = Field(ge=0)
    rejected_records: int = Field(ge=0)
    issues: list[EvidenceValidationIssue] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_record_counts(self) -> EvidenceValidationReport:
        if self.accepted_records + self.rejected_records != self.total_records:
            raise ValueError(
                "accepted_records plus rejected_records must equal total_records"
            )
        return self


class ValidatedBatchRecord(BaseModel):
    """A row that passed the selected Step 3 validation profile."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: UUID
    source_type: EvidenceSource
    dataset_profile: str
    validator_version: str
    row_number: int = Field(ge=1)
    record: dict[str, Any]
    raw_record_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class EvidenceValidationOutcome(BaseModel):
    """Validation report plus only the rows authorized for normalization."""

    report: EvidenceValidationReport
    accepted_records: list[ValidatedBatchRecord] = Field(default_factory=list)


TelemetryScalar = str | int | float | bool | None
SafeIdentifier = Annotated[str, Field(min_length=1, max_length=128)]
_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9._:-]+$")


class LiveTelemetryInput(BaseModel):
    """Transport-neutral contract shared with the live collection phase."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"]
    case_id: int = Field(ge=1)
    source_id: SafeIdentifier
    device_id: SafeIdentifier
    event_type: Literal[
        "telemetry",
        "device_state",
        "authentication",
        "network",
        "command",
        "heartbeat",
    ]
    observed_at: datetime
    sequence: int | None = Field(default=None, ge=0)
    metrics: dict[str, TelemetryScalar] = Field(default_factory=dict, max_length=64)

    @field_validator("source_id", "device_id")
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        if not _SAFE_IDENTIFIER.fullmatch(value):
            raise ValueError("identifier contains unsupported characters")
        return value

    @field_validator("observed_at")
    @classmethod
    def normalize_observed_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at must include a timezone")
        return value.astimezone(timezone.utc)

    @field_validator("metrics")
    @classmethod
    def validate_metrics(cls, value: dict[str, TelemetryScalar]) -> dict[str, TelemetryScalar]:
        for key, metric in value.items():
            if not _SAFE_IDENTIFIER.fullmatch(key) or len(key) > 128:
                raise ValueError(f"invalid metric name: {key!r}")
            if isinstance(metric, float) and not math.isfinite(metric):
                raise ValueError(f"metric {key!r} must be finite")
        return value

    @model_validator(mode="after")
    def require_measurements_for_telemetry(self) -> LiveTelemetryInput:
        if self.event_type == "telemetry" and not self.metrics:
            raise ValueError("telemetry events must contain at least one metric")
        return self


class ValidatedLiveTelemetry(BaseModel):
    telemetry: LiveTelemetryInput
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
