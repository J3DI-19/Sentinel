from __future__ import annotations

import json
import math
from collections import defaultdict
from typing import Any

from pydantic import ValidationError

from app.visualization.schemas import VisualizationLayoutV1, parse_data_ref


_SEVERITY_ORDER = {"low": 1, "medium": 2, "high": 3, "critical": 4}


class VisualizationService:
    """Resolve validated layout references exclusively from persisted records."""

    def __init__(self, db):
        self.db = db

    def validate_layout(self, value: dict, allowed_refs: set[str] | None = None) -> VisualizationLayoutV1:
        try:
            layout = VisualizationLayoutV1.model_validate(value)
        except ValidationError as exc:
            raise ValueError("invalid_visualization_spec") from exc
        refs = {component.data_ref for component in layout.components}
        if allowed_refs is not None and not refs <= allowed_refs:
            raise ValueError("invalid_visualization_reference")
        return layout

    def resolve(self, layout: VisualizationLayoutV1) -> dict:
        datasets: dict[str, list[dict] | dict] = {}
        analysis_ids: dict[str, str] = {}
        for component in layout.components:
            case_id, selector, dataset = parse_data_ref(component.data_ref)
            analysis_id = self._analysis_id(case_id, selector)
            datasets[component.id] = self._dataset(case_id, analysis_id, dataset)
            analysis_ids[component.id] = analysis_id
        return {
            "schema_version": "1.0",
            "layout": layout.model_dump(mode="json"),
            "datasets": datasets,
            "analysis_ids": analysis_ids,
        }

    def available_refs(self, case_id: int, selector: str = "latest") -> list[str]:
        # Resolve first so nonexistent cases/snapshots are never advertised to Qwen.
        self._analysis_id(case_id, selector)
        return [
            f"case:{case_id}:analysis:{selector}:{kind}"
            for kind in ("timeline", "risk_breakdown", "event_activity", "entity_graph", "evidence_table", "alert_list")
        ]

    def fallback(self, case_id: int, intent: str = "overview", selector: str = "latest") -> VisualizationLayoutV1:
        self._analysis_id(case_id, selector)
        selected = {
            "timeline": [("timeline", "Investigation timeline", 3, "tall")],
            "risk": [("risk_breakdown", "Risk breakdown", 2, "standard")],
            "correlation": [("entity_graph", "Entity correlations", 3, "tall")],
            "alerts": [("alert_list", "Investigation alerts", 3, "standard")],
            "evidence": [("evidence_table", "Evidence activity", 3, "standard")],
            "live": [("event_activity", "Persisted live activity", 3, "standard")],
        }.get(intent, [
            ("event_activity", "Event activity", 2, "standard"),
            ("risk_breakdown", "Risk breakdown", 1, "standard"),
            ("alert_list", "Alerts", 3, "standard"),
        ])
        components = [
            {
                "id": f"fallback-{kind.replace('_', '-')}",
                "type": kind,
                "title": title,
                "data_ref": f"case:{case_id}:analysis:{selector}:{kind}",
                "span": span,
                "height": height,
            }
            for kind, title, span, height in selected
        ]
        return VisualizationLayoutV1.model_validate({
            "schema_version": "1.0",
            "layout_id": f"deterministic-{intent}",
            "title": "Deterministic investigation view",
            "components": components,
        })

    def _analysis_id(self, case_id: int, selector: str) -> str:
        case = self.db.execute("SELECT id FROM cases WHERE id=?", (case_id,)).fetchone()
        if not case:
            raise KeyError("case_not_found")
        if selector == "latest":
            row = self.db.execute(
                "SELECT analysis_id FROM analysis_runs WHERE case_id=? ORDER BY created_at DESC LIMIT 1",
                (case_id,),
            ).fetchone()
        else:
            row = self.db.execute(
                "SELECT analysis_id FROM analysis_runs WHERE case_id=? AND analysis_id=?",
                (case_id, selector),
            ).fetchone()
        if not row:
            raise KeyError("analysis_not_found")
        return str(row[0])

    def _artifacts(self, analysis_id: str, kind: str, limit: int) -> list[dict]:
        rows = self.db.execute(
            "SELECT payload_json FROM analysis_artifacts WHERE analysis_id=? AND kind=? "
            "ORDER BY COALESCE(occurred_at,''),item_id LIMIT ?",
            (analysis_id, kind, limit),
        ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def _dataset(self, case_id: int, analysis_id: str, kind: str) -> list[dict] | dict:
        if kind == "timeline":
            return self._timeline(analysis_id)
        if kind == "risk_breakdown":
            return self._risk(analysis_id)
        if kind == "event_activity":
            return self._activity(analysis_id)
        if kind == "entity_graph":
            return self._graph(analysis_id)
        if kind == "evidence_table":
            return self._evidence(case_id, analysis_id)
        if kind == "alert_list":
            return self._alerts(analysis_id)
        raise ValueError("unknown_visualization_component")

    def _timeline(self, analysis_id: str) -> list[dict]:
        return [
            {
                "id": item["entry_id"],
                "time": item.get("occurred_at") or item["ingested_at"],
                "title": item["title"],
                "description": f"Persisted {item['entry_type']} record",
                "type": item["entry_type"],
                "severity": str(item.get("severity") or "low").title(),
                "evidenceId": str(item.get("evidence_ids", [""])[0]) if item.get("evidence_ids") else None,
            }
            for item in self._artifacts(analysis_id, "timeline", 100)
        ]

    def _risk(self, analysis_id: str) -> list[dict]:
        findings = self._artifacts(analysis_id, "finding", 100)
        if not findings:
            return []
        finding = max(findings, key=lambda item: int(item.get("risk", {}).get("score", 0)))
        return [
            {"label": factor["name"].replace("_", " ").title(), "value": int(factor["score"])}
            for factor in finding.get("risk", {}).get("factors", [])
        ]

    def _activity(self, analysis_id: str) -> list[dict]:
        totals: dict[str, int] = defaultdict(int)
        for point in self._artifacts(analysis_id, "aggregate", 10000):
            if point.get("series") == "activity_minute":
                totals[str(point["category"])] += int(point["value"])
        alert_totals: dict[str, int] = defaultdict(int)
        for alert in self._artifacts(analysis_id, "alert", 500):
            value = str(alert.get("triggered_at", ""))[:16]
            if value:
                alert_totals[value] += 1
        return [
            {"label": minute, "Events": value, "Alerts": alert_totals.get(minute, 0)}
            for minute, value in sorted(totals.items())[:200]
        ]

    def _graph(self, analysis_id: str) -> dict:
        source_nodes = self._artifacts(analysis_id, "graph_node", 100)
        count = max(1, len(source_nodes))
        nodes = []
        for index, item in enumerate(source_nodes):
            angle = (2 * math.pi * index / count) - math.pi / 2
            nodes.append({
                "id": item["node_id"], "label": item["label"], "kind": item["kind"],
                "x": round(46 + 35 * math.cos(angle), 3), "y": round(46 + 35 * math.sin(angle), 3),
                "eventCount": item["event_count"], "maximumRisk": item["maximum_risk"],
            })
        node_ids = {item["id"] for item in nodes}
        edges = [
            {
                "from": item["source_node_id"], "to": item["target_node_id"],
                "label": ", ".join(item["relationships"]), "eventCount": item["event_count"],
            }
            for item in self._artifacts(analysis_id, "graph_edge", 200)
            if item["source_node_id"] in node_ids and item["target_node_id"] in node_ids
        ]
        return {"nodes": nodes, "edges": edges}

    def _evidence(self, case_id: int, analysis_id: str) -> list[dict]:
        severity_by_event: dict[str, str] = {}
        for finding in self._artifacts(analysis_id, "finding", 200):
            severity = str(finding.get("severity", "low"))
            for event_id in finding.get("event_ids", []):
                current = severity_by_event.get(str(event_id), "low")
                if _SEVERITY_ORDER.get(severity, 0) > _SEVERITY_ORDER.get(current, 0):
                    severity_by_event[str(event_id)] = severity
        snapshot_event_ids: list[str] = []
        for item in self._artifacts(analysis_id, "timeline", 1000):
            for event_id in item.get("event_ids", []):
                value = str(event_id)
                if value not in snapshot_event_ids:
                    snapshot_event_ids.append(value)
                if len(snapshot_event_ids) >= 100:
                    break
            if len(snapshot_event_ids) >= 100:
                break
        if not snapshot_event_ids:
            return []
        placeholders = ",".join("?" for _ in snapshot_event_ids)
        rows = self.db.execute(
            "SELECT event_id,COALESCE(observed_at,ingested_at),entity_id,event_type,origin "
            f"FROM canonical_events WHERE case_id=? AND event_id IN ({placeholders}) "
            "ORDER BY COALESCE(observed_at,ingested_at),event_id LIMIT 100",
            (case_id, *snapshot_event_ids),
        ).fetchall()
        return [
            {
                "id": row[0], "time": row[1], "device": row[2] or "Unknown",
                "event": row[3], "origin": row[4],
                "severity": severity_by_event.get(str(row[0]), "low").title(),
            }
            for row in rows
        ]

    def _alerts(self, analysis_id: str) -> list[dict]:
        return [
            {
                "id": item["alert_id"], "time": item["triggered_at"], "title": item["title"],
                "severity": str(item["severity"]).title(), "risk": item["risk_score"],
                "status": item.get("workflow_status", "pending"),
            }
            for item in self._artifacts(analysis_id, "alert", 100)
        ]
