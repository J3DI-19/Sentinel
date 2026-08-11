from __future__ import annotations

import math
from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.analysis.config import AnalysisConfig


ANALYSIS_VERSION = "1.0"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskBand(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SortField(str, Enum):
    OBSERVED_AT = "observed_at"
    INGESTED_AT = "ingested_at"
    EVENT_TYPE = "event_type"
    EVENT_ID = "event_id"


class SortDirection(str, Enum):
    ASCENDING = "asc"
    DESCENDING = "desc"


class EventFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_types: list[str] = Field(default_factory=list, max_length=64)
    origins: list[Literal["batch", "live"]] = Field(default_factory=list, max_length=2)
    device_ids: list[str] = Field(default_factory=list, max_length=128)
    source_labels: list[str] = Field(default_factory=list, max_length=128)
    observed_from: datetime | None = None
    observed_to: datetime | None = None
    sort_field: SortField = SortField.OBSERVED_AT
    sort_direction: SortDirection = SortDirection.ASCENDING

    @field_validator("event_types", "origins", "device_ids", "source_labels")
    @classmethod
    def canonicalize_filter_values(cls, values: list[str]) -> list[str]:
        if any(not value or len(value) > 256 for value in values):
            raise ValueError("filter values must contain 1 to 256 characters")
        return sorted(set(values))

    @field_validator("observed_from", "observed_to")
    @classmethod
    def normalize_filter_time(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("filter timestamps must include a timezone")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_time_range(self) -> EventFilter:
        if self.observed_from and self.observed_to and self.observed_from > self.observed_to:
            raise ValueError("observed_from must not be after observed_to")
        return self


class ConditionTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    condition: str = Field(min_length=1, max_length=256)
    field: str = Field(min_length=1, max_length=128)
    operator: str = Field(min_length=1, max_length=32)
    expected: str = Field(max_length=256)
    actual: str = Field(max_length=256)
    matched: bool


class BaselineSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    baseline_id: UUID
    entity_id: str = Field(min_length=1, max_length=256)
    metric: str = Field(min_length=1, max_length=128)
    sample_event_ids: list[UUID] = Field(min_length=1, max_length=256)
    sample_count: int = Field(ge=1)
    mean: float
    population_stddev: float = Field(ge=0)
    threshold: float
    evaluated_event_id: UUID
    window_start: datetime
    window_end: datetime
    baseline_version: Literal["1.0"] = ANALYSIS_VERSION

    @field_validator("mean", "population_stddev", "threshold")
    @classmethod
    def require_finite_number(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("baseline values must be finite")
        return value

    @field_validator("window_start", "window_end")
    @classmethod
    def require_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("baseline timestamps must include a timezone")
        return value.astimezone(timezone.utc)


class RiskFactor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Literal[
        "severity",
        "confidence",
        "repetition",
        "device_criticality",
        "corroboration",
    ]
    score: int = Field(ge=0, le=100)
    weight: int = Field(ge=0, le=100)
    weighted_points: int = Field(ge=0, le=100)
    explanation: str = Field(min_length=1, max_length=512)


class RiskScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: int = Field(ge=0, le=100)
    band: RiskBand
    factors: list[RiskFactor] = Field(min_length=5, max_length=5)
    scoring_version: Literal["1.0"] = ANALYSIS_VERSION

    @model_validator(mode="after")
    def validate_factor_total(self) -> RiskScore:
        if sum(factor.weight for factor in self.factors) != 100:
            raise ValueError("risk factor weights must total 100")
        if sum(factor.weighted_points for factor in self.factors) != self.score:
            raise ValueError("risk factor points must total the risk score")
        return self


class DetectionFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finding_id: UUID
    case_id: int = Field(ge=1)
    rule_id: str = Field(min_length=1, max_length=64)
    rule_version: str = Field(min_length=1, max_length=32)
    title: str = Field(min_length=1, max_length=256)
    summary: str = Field(min_length=1, max_length=1024)
    severity: Severity
    confidence: int = Field(ge=0, le=100)
    event_ids: list[UUID] = Field(min_length=1, max_length=512)
    trigger_event_ids: list[UUID] = Field(min_length=1, max_length=512)
    evidence_ids: list[UUID] = Field(min_length=1, max_length=512)
    condition_trace: list[ConditionTrace] = Field(min_length=1, max_length=64)
    risk: RiskScore
    live_detected: bool

    @model_validator(mode="after")
    def validate_trigger_events(self) -> DetectionFinding:
        if not set(self.trigger_event_ids) <= set(self.event_ids):
            raise ValueError("trigger events must be included in supporting event IDs")
        return self


class Alert(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alert_id: UUID
    case_id: int = Field(ge=1)
    finding_id: UUID
    rule_id: str
    title: str
    severity: Severity
    risk_score: int = Field(ge=0, le=100)
    event_ids: list[UUID] = Field(min_length=1, max_length=512)
    evidence_ids: list[UUID] = Field(min_length=1, max_length=512)
    triggered_at: datetime
    delivery_status: Literal["pending"] = "pending"

    @field_validator("triggered_at")
    @classmethod
    def normalize_trigger_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("alert timestamps must include a timezone")
        return value.astimezone(timezone.utc)


class CorrelationReason(str, Enum):
    SHARED_DEVICE = "shared_device"
    SHARED_ACTOR = "shared_actor"
    SHARED_TARGET = "shared_target"
    SHARED_NETWORK_ADDRESS = "shared_network_address"


class CorrelationEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edge_id: UUID
    source_event_id: UUID
    target_event_id: UUID
    reasons: list[CorrelationReason] = Field(min_length=1, max_length=4)
    difference_seconds: float = Field(ge=0)
    window_seconds: int = Field(ge=1)
    correlation_version: Literal["1.0"] = ANALYSIS_VERSION


class Incident(BaseModel):
    model_config = ConfigDict(extra="forbid")

    incident_id: UUID
    case_id: int = Field(ge=1)
    event_ids: list[UUID] = Field(min_length=1, max_length=4096)
    finding_ids: list[UUID] = Field(min_length=1, max_length=1024)
    alert_ids: list[UUID] = Field(default_factory=list, max_length=1024)
    correlation_edge_ids: list[UUID] = Field(default_factory=list, max_length=4096)
    started_at: datetime | None
    ended_at: datetime | None
    maximum_risk: int = Field(ge=0, le=100)
    incident_version: Literal["1.0"] = ANALYSIS_VERSION

    @field_validator("started_at", "ended_at")
    @classmethod
    def normalize_incident_time(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("incident timestamps must include a timezone")
        return value.astimezone(timezone.utc)


class TimelineEntryType(str, Enum):
    EVENT = "event"
    ALERT = "alert"
    FINDING = "finding"


class TimelineEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entry_id: str = Field(min_length=1, max_length=256)
    entry_type: TimelineEntryType
    occurred_at: datetime | None
    ingested_at: datetime
    timestamp_basis: Literal["observed", "unavailable"]
    title: str = Field(min_length=1, max_length=256)
    event_ids: list[UUID] = Field(default_factory=list, max_length=512)
    evidence_ids: list[UUID] = Field(default_factory=list, max_length=512)
    severity: Severity | None = None
    risk_score: int | None = Field(default=None, ge=0, le=100)

    @field_validator("occurred_at", "ingested_at")
    @classmethod
    def normalize_timeline_time(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timeline timestamps must include a timezone")
        return value.astimezone(timezone.utc)


class GraphNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str = Field(min_length=1, max_length=512)
    entity_id: str = Field(min_length=1, max_length=256)
    kind: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=256)
    event_count: int = Field(ge=1)
    maximum_risk: int = Field(ge=0, le=100)


class GraphEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edge_id: UUID
    source_node_id: str
    target_node_id: str
    relationships: list[str] = Field(min_length=1, max_length=32)
    event_ids: list[UUID] = Field(min_length=1, max_length=4096)
    event_count: int = Field(ge=1)


class GraphData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    graph_version: Literal["1.0"] = ANALYSIS_VERSION


class ChartPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    series: Literal[
        "event_type",
        "origin",
        "source_label",
        "finding_severity",
        "risk_band",
        "activity_minute",
    ]
    category: str = Field(min_length=1, max_length=256)
    value: int = Field(ge=0)
    subgroup: str | None = Field(default=None, max_length=128)


class AnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysis_id: UUID
    analysis_version: Literal["1.0"] = ANALYSIS_VERSION
    configuration_version: Literal["1.0"] = ANALYSIS_VERSION
    rule_set_version: Literal["1.0"] = ANALYSIS_VERSION
    configuration: AnalysisConfig
    case_id: int = Field(ge=1)
    input_event_count: int = Field(ge=0)
    analyzed_event_count: int = Field(ge=0)
    event_ids: list[UUID] = Field(default_factory=list)
    filter: EventFilter
    baselines: list[BaselineSummary] = Field(default_factory=list)
    findings: list[DetectionFinding] = Field(default_factory=list)
    alerts: list[Alert] = Field(default_factory=list)
    correlations: list[CorrelationEdge] = Field(default_factory=list)
    incidents: list[Incident] = Field(default_factory=list)
    timeline: list[TimelineEntry] = Field(default_factory=list)
    graph: GraphData
    chart_points: list[ChartPoint] = Field(default_factory=list)
