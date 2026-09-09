from __future__ import annotations

from app.analysis.aggregates import build_activity_windows, build_chart_points
from app.analysis.config import AnalysisConfig
from app.analysis.correlation import build_incidents, correlate
from app.analysis.detection import detect
from app.analysis.filters import apply_event_filter
from app.analysis.graph import build_graph
from app.analysis.helpers import stable_uuid
from app.analysis.risk import score_candidates
from app.analysis.schemas import Alert, AnalysisResult, EventFilter
from app.analysis.timeline import build_timeline
from app.normalization.schemas import CanonicalEvent, EventOrigin


class AnalysisService:
    def __init__(self, config: AnalysisConfig | None = None) -> None:
        self.config = config or AnalysisConfig()

    def analyze(
        self,
        *,
        case_id: int,
        events: list[CanonicalEvent],
        event_filter: EventFilter | None = None,
    ) -> AnalysisResult:
        if case_id < 1:
            raise ValueError("case_id must be positive")
        if any(event.case_id != case_id for event in events):
            raise ValueError("all canonical events must belong to the requested case")
        if len({event.event_id for event in events}) != len(events):
            raise ValueError("canonical event IDs must be unique within an analysis run")

        specification = event_filter or EventFilter()
        selected = apply_event_filter(events, specification)
        candidates, baselines = detect(selected, self.config)
        correlations = correlate(selected, self.config)
        findings = score_candidates(
            candidates,
            correlations,
            self.config,
            case_id=case_id,
        )
        event_by_id = {event.event_id: event for event in selected}
        alerts = self._build_live_alerts(findings, event_by_id)
        incidents = build_incidents(
            case_id=case_id,
            events=selected,
            findings=findings,
            alerts=alerts,
            correlations=correlations,
            config=self.config,
        )
        event_ids = [event.event_id for event in selected]
        filter_material = specification.model_dump_json()
        configuration_material = self.config.model_dump_json()
        return AnalysisResult(
            analysis_id=stable_uuid(
                "analysis",
                case_id,
                configuration_material,
                filter_material,
                *(str(event_id) for event_id in event_ids),
            ),
            rule_set_version=self.config.rule_set_version,
            case_id=case_id,
            configuration=self.config,
            input_event_count=len(events),
            analyzed_event_count=len(selected),
            event_ids=event_ids,
            filter=specification,
            baselines=baselines,
            findings=findings,
            alerts=alerts,
            correlations=correlations,
            incidents=incidents,
            timeline=build_timeline(selected, findings, alerts),
            graph=build_graph(selected, findings),
            chart_points=build_chart_points(selected, findings),
            activity_windows=build_activity_windows(selected, findings, incidents),
        )

    def _build_live_alerts(self, findings, event_by_id) -> list[Alert]:
        alerts: list[Alert] = []
        for finding in findings:
            live_events = [
                event_by_id[event_id]
                for event_id in finding.trigger_event_ids
                if event_by_id[event_id].provenance.origin == EventOrigin.LIVE
            ]
            if not live_events:
                continue
            triggered_at = max(
                event.observed_at or event.ingested_at for event in live_events
            )
            alerts.append(
                Alert(
                    alert_id=stable_uuid(
                        "alert", finding.finding_id, self.config.rule_set_version
                    ),
                    case_id=finding.case_id,
                    finding_id=finding.finding_id,
                    rule_id=finding.rule_id,
                    title=finding.title,
                    severity=finding.severity,
                    risk_score=finding.risk.score,
                    event_ids=finding.event_ids,
                    evidence_ids=finding.evidence_ids,
                    triggered_at=triggered_at,
                )
            )
        return sorted(alerts, key=lambda alert: str(alert.alert_id))
