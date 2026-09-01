from __future__ import annotations

import math
from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, IPvAnyAddress, field_validator, model_validator


CANONICAL_SCHEMA_VERSION = "1.0"
NORMALIZATION_VERSION = "1.0"
CanonicalScalar = str | int | float | bool | None


class CanonicalSourceType(str, Enum):
    CASAS = "casas"
    CASAS_SMART_HOME = "casas_smart_home"
    TON_IOT_TELEMETRY = "ton_iot_telemetry"
    TON_IOT_FRIDGE_TELEMETRY = "ton_iot_fridge_telemetry"
    SIMULATION = "simulation"
    SIMULATED = "simulated"
    TON_IOT_NETWORK = "ton_iot_network"
    CICIOT2023_NETWORK = "ciciot2023_network"
    GENERIC = "generic"
    LIVE_TELEMETRY = "live_telemetry"


class EventOrigin(str, Enum):
    BATCH = "batch"
    LIVE = "live"


class NormalizationStatus(str, Enum):
    NORMALIZED = "normalized"
    REJECTED = "rejected"


class EntityKind(str, Enum):
    DEVICE = "device"
    IP_ADDRESS = "ip_address"
    USER = "user"
    SERVICE = "service"
    SOURCE = "source"
    UNKNOWN = "unknown"


class NormalizationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    field: str | None = None
    source_value: str | None = Field(default=None, max_length=256)


class CanonicalEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=256)
    kind: EntityKind
    name: str | None = Field(default=None, max_length=256)
    device_type: str | None = Field(default=None, max_length=128)
    ip: IPvAnyAddress | None = None
    mac: str | None = Field(default=None, pattern=r"^(?:[0-9a-f]{2}:){5}[0-9a-f]{2}$")


class CanonicalNetwork(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_ip: IPvAnyAddress | None = None
    source_port: int | None = Field(default=None, ge=0, le=65535)
    destination_ip: IPvAnyAddress | None = None
    destination_port: int | None = Field(default=None, ge=0, le=65535)
    protocol: str | None = Field(default=None, pattern=r"^[a-z0-9_.-]{1,32}$")
    bytes_sent: int | None = Field(default=None, ge=0)
    bytes_received: int | None = Field(default=None, ge=0)
    packets_sent: int | None = Field(default=None, ge=0)
    packets_received: int | None = Field(default=None, ge=0)


class CanonicalProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: UUID
    origin: EventOrigin
    source_type: CanonicalSourceType
    source_name: str = Field(min_length=1, max_length=512)
    source_id: str | None = Field(default=None, max_length=256)
    source_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_record_reference: str = Field(min_length=1, max_length=256)
    raw_record_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    adapter_name: str = Field(min_length=1, max_length=128)
    adapter_version: str = Field(min_length=1, max_length=32)
    normalization_version: Literal["1.0"] = NORMALIZATION_VERSION


class CanonicalEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = CANONICAL_SCHEMA_VERSION
    event_id: UUID
    case_id: int = Field(ge=1)
    observed_at: datetime | None
    ingested_at: datetime
    event_type: str = Field(pattern=r"^[a-z0-9_]{1,64}$")
    source_event_type: str | None = Field(default=None, max_length=256)
    source_label: str | None = Field(default=None, max_length=256)
    device: CanonicalEntity | None = None
    actor: CanonicalEntity | None = None
    target: CanonicalEntity | None = None
    network: CanonicalNetwork | None = None
    action: str | None = Field(default=None, pattern=r"^[a-z0-9_]{1,64}$")
    outcome: str | None = Field(default=None, pattern=r"^[a-z0-9_]{1,64}$")
    attributes: dict[str, CanonicalScalar] = Field(default_factory=dict, max_length=256)
    provenance: CanonicalProvenance
    normalization_warnings: list[NormalizationIssue] = Field(default_factory=list)

    @field_validator("observed_at", "ingested_at")
    @classmethod
    def require_utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("canonical timestamps must include a timezone")
        return value.astimezone(timezone.utc)

    @field_validator("attributes")
    @classmethod
    def reject_non_finite_attributes(
        cls, value: dict[str, CanonicalScalar]
    ) -> dict[str, CanonicalScalar]:
        for key, attribute in value.items():
            if isinstance(attribute, float) and not math.isfinite(attribute):
                raise ValueError(f"attribute {key!r} must be finite")
        return value


class NormalizationContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: int = Field(ge=1)
    evidence_id: UUID
    source_type: CanonicalSourceType
    origin: EventOrigin
    source_name: str = Field(min_length=1, max_length=512)
    source_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_record_reference: str = Field(min_length=1, max_length=256)
    ingested_at: datetime
    source_id: str | None = Field(default=None, max_length=256)

    @field_validator("ingested_at")
    @classmethod
    def normalize_ingested_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("ingested_at must include a timezone")
        return value.astimezone(timezone.utc)


class NormalizationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: NormalizationStatus
    source_record_reference: str
    event: CanonicalEvent | None = None
    issues: list[NormalizationIssue] = Field(default_factory=list)

    @model_validator(mode="after")
    def enforce_status_payload(self) -> NormalizationResult:
        if self.status == NormalizationStatus.NORMALIZED and self.event is None:
            raise ValueError("normalized results must contain an event")
        if self.status == NormalizationStatus.REJECTED and self.event is not None:
            raise ValueError("rejected results cannot contain an event")
        if self.status == NormalizationStatus.REJECTED and not self.issues:
            raise ValueError("rejected results must explain the failure")
        return self
