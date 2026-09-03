from __future__ import annotations

from datetime import datetime
from typing import Generic, Literal, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from app.analysis.schemas import GraphEdge, GraphNode
from app.evidence.schemas import EvidenceSource, EvidenceValidationReport
from app.normalization.schemas import CanonicalEvent


T = TypeVar("T")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PageResponse(StrictModel, Generic[T]):
    items: list[T]
    page: int = Field(ge=1)
    page_size: int = Field(ge=0)
    total: int = Field(ge=0)


class CasePublic(StrictModel):
    id: int = Field(ge=1)
    name: str
    description: str
    case_type: str
    status: str
    owner: str
    created_at: datetime
    updated_at: datetime | None = None


class CaseSummaryPublic(StrictModel):
    case: CasePublic
    event_count: int = Field(ge=0)
    entity_count: int = Field(ge=0)
    finding_count: int = Field(ge=0)
    alert_count: int = Field(ge=0)
    incident_count: int = Field(ge=0)
    maximum_risk: int = Field(ge=0, le=100)
    analysis_id: UUID | None


class ImportProgress(StrictModel):
    mode: Literal["indeterminate"]


class ImportErrorPublic(StrictModel):
    code: str
    message: str
    retryable: bool


class ImportPublic(StrictModel):
    import_id: UUID
    case_id: int = Field(ge=1)
    evidence_id: UUID | None
    filename: str
    source_type: EvidenceSource
    state: str
    progress: ImportProgress
    validation: EvidenceValidationReport | None
    error: ImportErrorPublic | None
    created_at: datetime
    updated_at: datetime


class EvidencePublic(StrictModel):
    evidence_id: UUID
    case_id: int = Field(ge=1)
    original_filename: str
    sanitized_filename: str
    media_type: str | None
    byte_size: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_type: EvidenceSource
    dataset_profile: str
    validator_version: str
    validation_status: str
    total_records: int = Field(ge=0)
    accepted_records: int = Field(ge=0)
    rejected_records: int = Field(ge=0)
    received_at: datetime
    committed_at: datetime | None = None


class ValidationIssuePublic(StrictModel):
    level: str
    code: str
    message: str
    row_number: int | None
    field: str | None
    rejected_value: str | None


class EvidenceDetailPublic(EvidencePublic):
    issues: list[ValidationIssuePublic]


class EventPublic(CanonicalEvent):
    raw_record: dict[str, JsonValue]


class AnalysisSnapshotPublic(StrictModel):
    analysis_id: UUID
    case_id: int = Field(ge=1)
    status: str
    created_at: datetime
    input_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_event_count: int = Field(ge=0)
    finding_count: int = Field(ge=0)
    alert_count: int = Field(ge=0)
    incident_count: int = Field(ge=0)
    maximum_risk: int = Field(ge=0, le=100)
    is_latest: bool


class ReanalysisPublic(AnalysisSnapshotPublic):
    reused_existing: bool


class GraphPublic(StrictModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    truncated: bool


class DashboardSummaryPublic(StrictModel):
    case_count: int = Field(ge=0)
    event_count: int = Field(ge=0)
    active_cases: int = Field(ge=0)
    recent_cases: list[CasePublic]
