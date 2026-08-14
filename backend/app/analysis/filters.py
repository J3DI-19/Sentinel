from __future__ import annotations

from app.analysis.schemas import EventFilter, SortDirection, SortField
from app.normalization.schemas import CanonicalEvent


def apply_event_filter(
    events: list[CanonicalEvent], specification: EventFilter
) -> list[CanonicalEvent]:
    event_types = set(specification.event_types)
    origins = set(specification.origins)
    device_ids = set(specification.device_ids)
    source_labels = set(specification.source_labels)

    selected = [
        event
        for event in events
        if (not event_types or event.event_type in event_types)
        and (not origins or event.provenance.origin.value in origins)
        and (
            not device_ids
            or (event.device is not None and event.device.id in device_ids)
            or (event.target is not None and event.target.id in device_ids)
        )
        and (not source_labels or event.source_label in source_labels)
        and (
            specification.observed_from is None
            or (
                event.observed_at is not None
                and event.observed_at >= specification.observed_from
            )
        )
        and (
            specification.observed_to is None
            or (
                event.observed_at is not None
                and event.observed_at <= specification.observed_to
            )
        )
    ]
    return stable_sort(selected, specification)


def stable_sort(
    events: list[CanonicalEvent], specification: EventFilter
) -> list[CanonicalEvent]:
    descending = specification.sort_direction == SortDirection.DESCENDING
    if specification.sort_field == SortField.OBSERVED_AT:
        timed = [event for event in events if event.observed_at is not None]
        untimed = [event for event in events if event.observed_at is None]
        timed.sort(
            key=lambda event: (event.observed_at, event.ingested_at, str(event.event_id)),
            reverse=descending,
        )
        untimed.sort(
            key=lambda event: (event.ingested_at, str(event.event_id)),
            reverse=descending,
        )
        return timed + untimed
    if specification.sort_field == SortField.INGESTED_AT:
        key = lambda event: (event.ingested_at, str(event.event_id))
    elif specification.sort_field == SortField.EVENT_TYPE:
        key = lambda event: (event.event_type, str(event.event_id))
    else:
        key = lambda event: (str(event.event_id),)
    return sorted(events, key=key, reverse=descending)
