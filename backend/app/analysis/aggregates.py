from __future__ import annotations

import pandas as pd

from collections import Counter, defaultdict
from datetime import datetime
from statistics import median

from app.analysis.helpers import primary_entity_id
from app.analysis.schemas import (
    ActivityClassificationCount,
    ActivityWindowExplanation,
    ChartPoint,
    ClassificationSource,
    DetectionFinding,
    Incident,
)
from app.normalization.schemas import CanonicalEvent


def build_chart_points(
    events: list[CanonicalEvent], findings: list[DetectionFinding]
) -> list[ChartPoint]:
    points: list[ChartPoint] = []
    event_rows = [
        {
            "event_type": event.event_type,
            "origin": event.provenance.origin.value,
            "source_label": event.source_label,
            "attack_class": event.attributes.get("attack_type"),
            "observed_at": event.observed_at,
        }
        for event in events
    ]
    if event_rows:
        frame = pd.DataFrame(event_rows)
        points.extend(_count_series(frame, "event_type", "event_type"))
        points.extend(_count_series(frame, "origin", "origin"))
        labelled = frame.dropna(subset=["source_label"])
        if not labelled.empty:
            points.extend(_count_series(labelled, "source_label", "source_label"))
        classified = frame.dropna(subset=["attack_class"])
        if not classified.empty:
            points.extend(_count_series(classified, "attack_class", "attack_class"))
        timed = frame.dropna(subset=["observed_at"]).copy()
        if not timed.empty:
            timed["minute"] = pd.to_datetime(timed["observed_at"], utc=True).dt.floor("min")
            grouped = (
                timed.groupby(["minute", "origin"], sort=True, dropna=False)
                .size()
                .reset_index(name="value")
            )
            points.extend(
                ChartPoint(
                    series="activity_minute",
                    category=row.minute.isoformat(),
                    subgroup=str(row.origin),
                    value=int(row.value),
                )
                for row in grouped.itertuples(index=False)
            )

    if findings:
        frame = pd.DataFrame(
            {
                "severity": [finding.severity.value for finding in findings],
                "risk_band": [finding.risk.band.value for finding in findings],
            }
        )
        points.extend(_count_series(frame, "severity", "finding_severity"))
        points.extend(_count_series(frame, "risk_band", "risk_band"))
    return sorted(
        points,
        key=lambda point: (point.series, point.category, point.subgroup or ""),
    )


def _count_series(frame: pd.DataFrame, column: str, series: str) -> list[ChartPoint]:
    counts = frame.groupby(column, sort=True, dropna=False).size()
    return [
        ChartPoint(series=series, category=str(category), value=int(value))
        for category, value in counts.items()
    ]


def build_activity_windows(
    events: list[CanonicalEvent],
    findings: list[DetectionFinding],
    incidents: list[Incident],
) -> list[ActivityWindowExplanation]:
    """Explain volume by minute without claiming that volume establishes causation."""
    grouped: dict[datetime, list[CanonicalEvent]] = defaultdict(list)
    for event in events:
        if event.observed_at is not None:
            grouped[event.observed_at.replace(second=0, microsecond=0)].append(event)
    if not grouped:
        return []
    baseline = float(median(len(values) for values in grouped.values()))
    finding_by_event: dict[object, set] = defaultdict(set)
    for finding in findings:
        for event_id in finding.event_ids:
            finding_by_event[event_id].add(finding.finding_id)
    incident_by_event: dict[object, set] = defaultdict(set)
    for incident in incidents:
        for event_id in incident.event_ids:
            incident_by_event[event_id].add(incident.incident_id)
    explanations = []
    for minute, window_events in sorted(grouped.items()):
        event_types = Counter(event.event_type for event in window_events)
        devices = Counter(primary_entity_id(event) or "unknown" for event in window_events)
        classes = Counter(
            str(event.attributes["attack_type"])
            for event in window_events
            if event.attributes.get("attack_type") not in (None, "", "normal")
        )
        count = len(window_events)
        ratio = round(count / baseline, 3) if baseline else None
        anomalous = count >= 5 and (baseline == 0 or count >= baseline * 3)
        finding_ids = sorted(
            {item for event in window_events for item in finding_by_event[event.event_id]},
            key=str,
        )
        incident_ids = sorted(
            {item for event in window_events for item in incident_by_event[event.event_id]},
            key=str,
        )
        if classes:
            cause_status = "source_classified"
            dominant, dominant_count = classes.most_common(1)[0]
            explanation = (
                f"{dominant_count} of {count} events carry the source-supplied attack class "
                f"{dominant!r}; this is dataset provenance, not an independently inferred cause."
            )
        elif finding_ids:
            cause_status = "rule_context"
            explanation = (
                f"{len(finding_ids)} deterministic finding(s) overlap this minute; inspect their "
                "condition traces before attributing the activity increase."
            )
        else:
            cause_status = "undetermined"
            explanation = "No source classification or deterministic finding explains this activity window."
        explanations.append(ActivityWindowExplanation(
            window_id=minute.isoformat(),
            window_start=minute,
            event_count=count,
            baseline_count=baseline,
            deviation_ratio=ratio,
            is_volume_anomaly=anomalous,
            cause_status=cause_status,
            explanation=explanation,
            top_event_types=dict(event_types.most_common(5)),
            top_devices=dict(devices.most_common(5)),
            source_classifications=[
                ActivityClassificationCount(
                    value=value,
                    count=value_count,
                    provenance=ClassificationSource.DATASET_LABEL,
                )
                for value, value_count in classes.most_common(10)
            ],
            finding_ids=finding_ids,
            incident_ids=incident_ids,
        ))
    return explanations
