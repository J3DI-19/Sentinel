from __future__ import annotations

from datetime import datetime
from typing import Iterable
from uuid import UUID, uuid5

from app.normalization.schemas import CanonicalEntity, CanonicalEvent


ANALYSIS_NAMESPACE = UUID("4e2876c6-c360-5a56-a2bf-61008da4ff2d")


def stable_uuid(kind: str, *parts: object) -> UUID:
    material = "|".join((kind, *(str(part) for part in parts)))
    return uuid5(ANALYSIS_NAMESPACE, material)


def unique_sorted_uuids(values: Iterable[UUID]) -> list[UUID]:
    return sorted(set(values), key=str)


def primary_entity_id(event: CanonicalEvent) -> str | None:
    for entity in (event.device, event.target, event.actor):
        if entity is not None:
            return entity.id
    return None


def effective_ingestion_order(event: CanonicalEvent) -> tuple[datetime, str]:
    return event.ingested_at, str(event.event_id)


def observed_order(event: CanonicalEvent) -> tuple[bool, datetime, datetime, str]:
    return (
        event.observed_at is None,
        event.observed_at or event.ingested_at,
        event.ingested_at,
        str(event.event_id),
    )


def entity_node_id(entity: CanonicalEntity) -> str:
    return f"{entity.kind.value}:{entity.id}"


def event_entities(event: CanonicalEvent) -> list[tuple[str, CanonicalEntity]]:
    entities: list[tuple[str, CanonicalEntity]] = []
    seen: set[str] = set()
    for role, entity in (
        ("device", event.device),
        ("actor", event.actor),
        ("target", event.target),
    ):
        if entity is None:
            continue
        node_id = entity_node_id(entity)
        if node_id not in seen:
            entities.append((role, entity))
            seen.add(node_id)
    return entities
