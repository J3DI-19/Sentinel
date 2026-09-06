from __future__ import annotations

import networkx as nx

from app.analysis.config import AnalysisConfig
from app.analysis.detection import DetectionCandidate
from app.analysis.helpers import stable_uuid, unique_sorted_uuids
from app.analysis.schemas import (
    Alert,
    CorrelationEdge,
    CorrelationReason,
    DetectionFinding,
    INCIDENT_CORRELATION_EDGE_REFERENCE_LIMIT,
    Incident,
)
from app.normalization.schemas import CanonicalEntity, CanonicalEvent


def correlate(
    events: list[CanonicalEvent], config: AnalysisConfig
) -> list[CorrelationEdge]:
    timed = sorted(
        (event for event in events if event.observed_at is not None),
        key=lambda event: (event.observed_at, str(event.event_id)),
    )
    edges: list[CorrelationEdge] = []
    for left_index, left in enumerate(timed):
        for right in timed[left_index + 1 :]:
            difference = (right.observed_at - left.observed_at).total_seconds()
            if difference > config.correlation_window_seconds:
                break
            reasons = _correlation_reasons(left, right)
            if not reasons:
                continue
            edges.append(
                CorrelationEdge(
                    edge_id=stable_uuid(
                        "correlation",
                        left.event_id,
                        right.event_id,
                        *(reason.value for reason in reasons),
                        config.correlation_version,
                    ),
                    source_event_id=left.event_id,
                    target_event_id=right.event_id,
                    reasons=reasons,
                    difference_seconds=round(difference, 6),
                    window_seconds=config.correlation_window_seconds,
                )
            )
    return sorted(edges, key=lambda edge: str(edge.edge_id))


def build_incidents(
    *,
    case_id: int,
    events: list[CanonicalEvent],
    findings: list[DetectionFinding],
    alerts: list[Alert],
    correlations: list[CorrelationEdge],
) -> list[Incident]:
    if not findings:
        return []
    event_by_id = {event.event_id: event for event in events}
    graph = nx.Graph()
    relevant_ids = {event_id for finding in findings for event_id in finding.event_ids}
    graph.add_nodes_from(event_by_id)
    for edge in correlations:
        graph.add_edge(edge.source_event_id, edge.target_event_id, edge_id=edge.edge_id)
    for finding in findings:
        anchor = finding.event_ids[0]
        for event_id in finding.event_ids[1:]:
            graph.add_edge(anchor, event_id, finding_id=finding.finding_id)

    incidents: list[Incident] = []
    for component in nx.connected_components(graph):
        if not component & relevant_ids:
            continue
        component_ids = unique_sorted_uuids(component)
        component_findings = [
            finding
            for finding in findings
            if any(event_id in component for event_id in finding.event_ids)
        ]
        if not component_findings:
            continue
        finding_ids = unique_sorted_uuids(finding.finding_id for finding in component_findings)
        component_alerts = [alert for alert in alerts if alert.finding_id in finding_ids]
        component_edges = [
            edge
            for edge in correlations
            if edge.source_event_id in component and edge.target_event_id in component
        ]
        component_edge_ids = [
            edge.edge_id
            for edge in sorted(
                component_edges,
                key=lambda edge: (
                    edge.difference_seconds,
                    str(edge.source_event_id),
                    str(edge.target_event_id),
                    str(edge.edge_id),
                ),
            )
        ]
        retained_edge_ids = component_edge_ids[
            :INCIDENT_CORRELATION_EDGE_REFERENCE_LIMIT
        ]
        observed = [
            event_by_id[event_id].observed_at
            for event_id in component_ids
            if event_id in event_by_id and event_by_id[event_id].observed_at is not None
        ]
        incidents.append(
            Incident(
                incident_id=stable_uuid(
                    "incident", case_id, *(str(event_id) for event_id in component_ids)
                ),
                case_id=case_id,
                event_ids=component_ids,
                finding_ids=finding_ids,
                alert_ids=unique_sorted_uuids(alert.alert_id for alert in component_alerts),
                correlation_edge_ids=retained_edge_ids,
                correlation_edge_count=len(component_edge_ids),
                correlation_edges_truncated=(
                    len(component_edge_ids) > len(retained_edge_ids)
                ),
                started_at=min(observed) if observed else None,
                ended_at=max(observed) if observed else None,
                maximum_risk=max(finding.risk.score for finding in component_findings),
            )
        )
    return sorted(
        incidents,
        key=lambda incident: (
            incident.started_at is None,
            incident.started_at or incident.ended_at,
            str(incident.incident_id),
        ),
    )


def corroboration_score(
    candidate: DetectionCandidate, correlations: list[CorrelationEdge]
) -> tuple[int, str]:
    event_ids = set(candidate.event_ids)
    touching = [
        edge
        for edge in correlations
        if edge.source_event_id in event_ids or edge.target_event_id in event_ids
    ]
    external = [
        edge
        for edge in touching
        if not ({edge.source_event_id, edge.target_event_id} <= event_ids)
    ]
    if external:
        return 100, f"{len(external)} correlation link(s) connect supporting and external events"
    if touching:
        return 75, f"{len(touching)} deterministic link(s) connect supporting events"
    if len(candidate.evidence_ids) > 1:
        return 50, "Supporting events span multiple evidence objects without a correlation edge"
    return 0, "No corroborating correlation link was present"


def _correlation_reasons(
    left: CanonicalEvent, right: CanonicalEvent
) -> list[CorrelationReason]:
    reasons: set[CorrelationReason] = set()
    if _same_entity(left.device, right.device):
        reasons.add(CorrelationReason.SHARED_DEVICE)
    if _same_entity(left.actor, right.actor):
        reasons.add(CorrelationReason.SHARED_ACTOR)
    if _same_entity(left.target, right.target):
        reasons.add(CorrelationReason.SHARED_TARGET)
    left_addresses = _network_addresses(left)
    right_addresses = _network_addresses(right)
    if left_addresses & right_addresses:
        reasons.add(CorrelationReason.SHARED_NETWORK_ADDRESS)
    return sorted(reasons, key=lambda reason: reason.value)


def _same_entity(
    left: CanonicalEntity | None, right: CanonicalEntity | None
) -> bool:
    return (
        left is not None
        and right is not None
        and left.kind == right.kind
        and left.id == right.id
    )


def _network_addresses(event: CanonicalEvent) -> set[str]:
    addresses: set[str] = set()
    for entity in (event.device, event.actor, event.target):
        if entity is not None and entity.ip is not None:
            addresses.add(str(entity.ip))
    if event.network is not None:
        if event.network.source_ip is not None:
            addresses.add(str(event.network.source_ip))
        if event.network.destination_ip is not None:
            addresses.add(str(event.network.destination_ip))
    return addresses
