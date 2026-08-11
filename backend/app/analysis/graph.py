from __future__ import annotations

from collections import defaultdict
from itertools import combinations

import networkx as nx

from app.analysis.helpers import entity_node_id, event_entities, stable_uuid
from app.analysis.schemas import DetectionFinding, GraphData, GraphEdge, GraphNode
from app.normalization.schemas import CanonicalEvent


def build_graph(
    events: list[CanonicalEvent], findings: list[DetectionFinding]
) -> GraphData:
    graph = nx.Graph()
    event_risk: dict[object, int] = defaultdict(int)
    for finding in findings:
        for event_id in finding.event_ids:
            event_risk[event_id] = max(event_risk[event_id], finding.risk.score)

    edge_events: dict[tuple[str, str], set] = defaultdict(set)
    edge_relationships: dict[tuple[str, str], set[str]] = defaultdict(set)
    node_events: dict[str, set] = defaultdict(set)
    node_risk: dict[str, int] = defaultdict(int)

    for event in events:
        entities = event_entities(event)
        for role, entity in entities:
            node_id = entity_node_id(entity)
            graph.add_node(
                node_id,
                entity_id=entity.id,
                kind=entity.kind.value,
                label=entity.name or entity.id,
            )
            node_events[node_id].add(event.event_id)
            node_risk[node_id] = max(node_risk[node_id], event_risk[event.event_id])

        for (left_role, left), (right_role, right) in combinations(entities, 2):
            left_id, right_id = sorted((entity_node_id(left), entity_node_id(right)))
            if left_id == right_id:
                continue
            relationship = _relationship(left_role, right_role, event)
            graph.add_edge(left_id, right_id)
            edge_events[(left_id, right_id)].add(event.event_id)
            edge_relationships[(left_id, right_id)].add(relationship)

        _add_network_relationships(
            graph,
            event,
            edge_events,
            edge_relationships,
            node_events,
            node_risk,
            event_risk[event.event_id],
        )

    nodes = [
        GraphNode(
            node_id=node_id,
            entity_id=attributes["entity_id"],
            kind=attributes["kind"],
            label=attributes["label"],
            event_count=len(node_events[node_id]),
            maximum_risk=node_risk[node_id],
        )
        for node_id, attributes in sorted(graph.nodes(data=True), key=lambda item: item[0])
    ]
    edges = [
        GraphEdge(
            edge_id=stable_uuid(
                "graph-edge",
                source,
                target,
                *(sorted(edge_relationships[(source, target)])),
            ),
            source_node_id=source,
            target_node_id=target,
            relationships=sorted(edge_relationships[(source, target)]),
            event_ids=sorted(edge_events[(source, target)], key=str),
            event_count=len(edge_events[(source, target)]),
        )
        for source, target in sorted(edge_events)
    ]
    return GraphData(nodes=nodes, edges=edges)


def _relationship(left_role: str, right_role: str, event: CanonicalEvent) -> str:
    if event.action:
        return event.action
    if event.network is not None:
        return "network_communication"
    return "_to_".join(sorted((left_role, right_role)))


def _add_network_relationships(
    graph: nx.Graph,
    event: CanonicalEvent,
    edge_events: dict,
    edge_relationships: dict,
    node_events: dict,
    node_risk: dict,
    risk: int,
) -> None:
    if (
        event.network is None
        or event.network.source_ip is None
        or event.network.destination_ip is None
    ):
        return
    source_ip = str(event.network.source_ip)
    destination_ip = str(event.network.destination_ip)
    source_id = f"ip_address:ip:{source_ip}"
    target_id = f"ip_address:ip:{destination_ip}"
    for node_id, address in ((source_id, source_ip), (target_id, destination_ip)):
        graph.add_node(
            node_id,
            entity_id=f"ip:{address}",
            kind="ip_address",
            label=address,
        )
        node_events[node_id].add(event.event_id)
        node_risk[node_id] = max(node_risk[node_id], risk)
    if source_id != target_id:
        left, right = sorted((source_id, target_id))
        graph.add_edge(left, right)
        edge_events[(left, right)].add(event.event_id)
        edge_relationships[(left, right)].add("network_communication")
