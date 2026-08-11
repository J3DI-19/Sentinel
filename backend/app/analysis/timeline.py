from __future__ import annotations

from app.analysis.schemas import (
    Alert,
    DetectionFinding,
    TimelineEntry,
    TimelineEntryType,
)
from app.normalization.schemas import CanonicalEvent


def build_timeline(
    events: list[CanonicalEvent],
    findings: list[DetectionFinding],
    alerts: list[Alert],
) -> list[TimelineEntry]:
    event_by_id = {event.event_id: event for event in events}
    entries = [
        TimelineEntry(
            entry_id=f"event:{event.event_id}",
            entry_type=TimelineEntryType.EVENT,
            occurred_at=event.observed_at,
            ingested_at=event.ingested_at,
            timestamp_basis="observed" if event.observed_at is not None else "unavailable",
            title=event.event_type,
            event_ids=[event.event_id],
            evidence_ids=[event.provenance.evidence_id],
        )
        for event in events
    ]
    for finding in findings:
        supporting = [event_by_id[event_id] for event_id in finding.event_ids]
        observed = [event.observed_at for event in supporting if event.observed_at is not None]
        entries.append(
            TimelineEntry(
                entry_id=f"finding:{finding.finding_id}",
                entry_type=TimelineEntryType.FINDING,
                occurred_at=max(observed) if observed else None,
                ingested_at=max(event.ingested_at for event in supporting),
                timestamp_basis="observed" if observed else "unavailable",
                title=finding.title,
                event_ids=finding.event_ids,
                evidence_ids=finding.evidence_ids,
                severity=finding.severity,
                risk_score=finding.risk.score,
            )
        )
    finding_by_id = {finding.finding_id: finding for finding in findings}
    for alert in alerts:
        finding = finding_by_id[alert.finding_id]
        supporting = [event_by_id[event_id] for event_id in finding.event_ids]
        observed = [event.observed_at for event in supporting if event.observed_at is not None]
        entries.append(
            TimelineEntry(
                entry_id=f"alert:{alert.alert_id}",
                entry_type=TimelineEntryType.ALERT,
                occurred_at=max(observed) if observed else None,
                ingested_at=alert.triggered_at,
                timestamp_basis="observed" if observed else "unavailable",
                title=alert.title,
                event_ids=alert.event_ids,
                evidence_ids=alert.evidence_ids,
                severity=alert.severity,
                risk_score=alert.risk_score,
            )
        )
    type_order = {
        TimelineEntryType.EVENT: 0,
        TimelineEntryType.FINDING: 1,
        TimelineEntryType.ALERT: 2,
    }
    return sorted(
        entries,
        key=lambda entry: (
            entry.occurred_at is None,
            entry.occurred_at or entry.ingested_at,
            entry.ingested_at,
            type_order[entry.entry_type],
            entry.entry_id,
        ),
    )
