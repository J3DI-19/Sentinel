from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RiskWeights(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    severity: int = Field(default=30, ge=0, le=100)
    confidence: int = Field(default=25, ge=0, le=100)
    repetition: int = Field(default=20, ge=0, le=100)
    device_criticality: int = Field(default=15, ge=0, le=100)
    corroboration: int = Field(default=10, ge=0, le=100)

    @model_validator(mode="after")
    def require_total_weight(self) -> RiskWeights:
        if sum(self.model_dump().values()) != 100:
            raise ValueError("risk weights must total 100")
        return self


class AnalysisConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    configuration_version: Literal["1.0"] = "1.0"
    rule_set_version: Literal["1.0"] = "1.0"
    baseline_version: Literal["1.0"] = "1.0"
    scoring_version: Literal["1.0"] = "1.0"
    correlation_version: Literal["1.0"] = "1.0"
    authentication_failure_threshold: int = Field(default=10, ge=2, le=1000)
    authentication_window_seconds: int = Field(default=60, ge=1, le=86400)
    request_rate_multiplier: float = Field(default=3.0, ge=1.0, le=1000)
    baseline_min_samples: int = Field(default=3, ge=2, le=1000)
    baseline_max_samples: int = Field(default=20, ge=2, le=10000)
    baseline_sigma: float = Field(default=3.0, ge=0.1, le=20)
    baseline_minimum_delta: float = Field(default=1.0, ge=0)
    correlation_window_seconds: int = Field(default=120, ge=1, le=86400)
    default_device_criticality: int = Field(default=50, ge=0, le=100)
    critical_device_scores: dict[str, int] = Field(default_factory=dict, max_length=1024)
    malicious_labels: tuple[str, ...] = Field(default=(
        "1",
        "attack",
        "backdoor",
        "ddos",
        "dos",
        "injection",
        "malicious",
        "malware",
        "password",
        "ransomware",
        "scanning",
        "xss",
    ), min_length=1, max_length=128)
    dataset_benign_labels: tuple[str, ...] = Field(
        default=("0", "benign", "benigntraffic", "normal"),
        min_length=1,
        max_length=32,
    )
    risk_weights: RiskWeights = Field(default_factory=RiskWeights)

    @field_validator("critical_device_scores")
    @classmethod
    def canonicalize_criticality(cls, values: dict[str, int]) -> dict[str, int]:
        if any(not key or len(key) > 256 for key in values):
            raise ValueError("critical device identifiers must contain 1 to 256 characters")
        return dict(sorted(values.items()))

    @field_validator("malicious_labels", "dataset_benign_labels")
    @classmethod
    def canonicalize_labels(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(sorted({value.strip().casefold() for value in values}))
        if any(not value or len(value) > 64 for value in normalized):
            raise ValueError("configured labels must contain 1 to 64 characters")
        return normalized

    @model_validator(mode="after")
    def validate_versions_and_windows(self) -> AnalysisConfig:
        if self.baseline_max_samples < self.baseline_min_samples:
            raise ValueError("baseline_max_samples must be at least baseline_min_samples")
        if any(not 0 <= score <= 100 for score in self.critical_device_scores.values()):
            raise ValueError("critical device scores must be between 0 and 100")
        return self
