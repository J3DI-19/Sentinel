from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.analysis.schemas import EventFilter
from app.evidence.schemas import EvidenceValidationReport
from app.normalization.schemas import CanonicalEvent, NormalizationIssue


class CaseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("case name cannot be blank")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class CaseRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: int = Field(ge=1)
    name: str
    description: str | None = None
    status: Literal["open", "closed"] = "open"
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class NormalizationFailure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_record_reference: str
    issues: list[NormalizationIssue] = Field(min_length=1)


class EvidenceIngestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    validation: EvidenceValidationReport
    normalized_event_count: int = Field(ge=0)
    events: list[CanonicalEvent] = Field(default_factory=list)
    normalization_failures: list[NormalizationFailure] = Field(default_factory=list)


class ReanalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filter: EventFilter = Field(default_factory=EventFilter)


class AnalysisRunSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysis_id: UUID
    case_id: int = Field(ge=1)
    analyzed_event_count: int = Field(ge=0)
    finding_count: int = Field(ge=0)
    alert_count: int = Field(ge=0)
    incident_count: int = Field(ge=0)
    filter: EventFilter
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
