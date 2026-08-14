"""Canonical event contracts and deterministic source adapters."""

from app.normalization.schemas import (
    CanonicalEvent,
    CanonicalSourceType,
    NormalizationContext,
    NormalizationResult,
)
from app.normalization.service import NormalizationService

__all__ = [
    "CanonicalEvent",
    "CanonicalSourceType",
    "NormalizationContext",
    "NormalizationResult",
    "NormalizationService",
]
