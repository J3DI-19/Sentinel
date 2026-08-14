from __future__ import annotations

from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP

from app.analysis.config import AnalysisConfig
from app.analysis.correlation import corroboration_score
from app.analysis.detection import DetectionCandidate
from app.analysis.helpers import stable_uuid
from app.analysis.schemas import (
    CorrelationEdge,
    DetectionFinding,
    RiskBand,
    RiskFactor,
    RiskScore,
    Severity,
)


_SEVERITY_SCORES = {
    Severity.LOW: 25,
    Severity.MEDIUM: 50,
    Severity.HIGH: 75,
    Severity.CRITICAL: 100,
}


def score_candidates(
    candidates: list[DetectionCandidate],
    correlations: list[CorrelationEdge],
    config: AnalysisConfig,
    *,
    case_id: int,
) -> list[DetectionFinding]:
    findings: list[DetectionFinding] = []
    for candidate in candidates:
        severity = _SEVERITY_SCORES[candidate.severity]
        repetition = min(
            100,
            _round_half_up(
                Decimal(candidate.repetition_count)
                * Decimal(100)
                / Decimal(max(1, candidate.repetition_threshold))
            ),
        )
        criticality = config.critical_device_scores.get(
            candidate.entity_id or "", config.default_device_criticality
        )
        corroboration, corroboration_explanation = corroboration_score(
            candidate, correlations
        )
        inputs = [
            (
                "severity",
                severity,
                config.risk_weights.severity,
                f"Rule severity {candidate.severity.value} maps to {severity}",
            ),
            (
                "confidence",
                candidate.confidence,
                config.risk_weights.confidence,
                f"Versioned rule confidence is {candidate.confidence}",
            ),
            (
                "repetition",
                repetition,
                config.risk_weights.repetition,
                f"{candidate.repetition_count} occurrence(s) against threshold {candidate.repetition_threshold}",
            ),
            (
                "device_criticality",
                criticality,
                config.risk_weights.device_criticality,
                f"Configured criticality for {candidate.entity_id or 'unknown entity'} is {criticality}",
            ),
            (
                "corroboration",
                corroboration,
                config.risk_weights.corroboration,
                corroboration_explanation,
            ),
        ]
        raw_points = [
            Decimal(score) * Decimal(weight) / Decimal(100)
            for _, score, weight, _ in inputs
        ]
        target_total = min(100, _round_half_up(sum(raw_points)))
        allocated = [int(value.quantize(Decimal("1"), rounding=ROUND_FLOOR)) for value in raw_points]
        remainder_order = sorted(
            range(len(raw_points)),
            key=lambda index: (-(raw_points[index] - allocated[index]), index),
        )
        for index in remainder_order[: target_total - sum(allocated)]:
            allocated[index] += 1
        factors = [
            RiskFactor(
                name=name,
                score=score,
                weight=weight,
                weighted_points=allocated[index],
                explanation=explanation,
            )
            for index, (name, score, weight, explanation) in enumerate(inputs)
        ]
        total = sum(factor.weighted_points for factor in factors)
        event_material = tuple(str(event_id) for event_id in candidate.event_ids)
        findings.append(
            DetectionFinding(
                finding_id=stable_uuid(
                    "finding",
                    case_id,
                    candidate.rule_id,
                    config.rule_set_version,
                    *event_material,
                ),
                case_id=case_id,
                rule_id=candidate.rule_id,
                rule_version=config.rule_set_version,
                title=candidate.title,
                summary=candidate.summary,
                severity=candidate.severity,
                confidence=candidate.confidence,
                event_ids=list(candidate.event_ids),
                trigger_event_ids=list(candidate.trigger_event_ids),
                evidence_ids=list(candidate.evidence_ids),
                condition_trace=list(candidate.condition_trace),
                risk=RiskScore(
                    score=total,
                    band=_risk_band(total),
                    factors=factors,
                ),
                live_detected=candidate.live_detected,
            )
        )
    return sorted(findings, key=lambda finding: str(finding.finding_id))


def _round_half_up(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _risk_band(score: int) -> RiskBand:
    if score >= 75:
        return RiskBand.CRITICAL
    if score >= 50:
        return RiskBand.HIGH
    if score >= 25:
        return RiskBand.MEDIUM
    return RiskBand.LOW
