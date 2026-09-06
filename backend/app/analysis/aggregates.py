from __future__ import annotations

import pandas as pd

from app.analysis.schemas import ChartPoint, DetectionFinding
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
