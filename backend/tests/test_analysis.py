from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.analysis.config import AnalysisConfig, RiskWeights
from app.analysis.schemas import EventFilter, SortDirection
from app.analysis.service import AnalysisService
from app.normalization.schemas import (
    CanonicalEntity,
    CanonicalEvent,
    CanonicalNetwork,
    CanonicalProvenance,
    CanonicalSourceType,
    EntityKind,
    EventOrigin,
)


BASE_TIME = datetime(2026, 7, 21, 14, 30, tzinfo=timezone.utc)


def canonical_event(
    index: int,
    *,
    seconds: int | None,
    event_type: str,
    origin: EventOrigin = EventOrigin.BATCH,
    device_id: str = "CAM-01",
    actor_ip: str | None = "185.77.12.44",
    source_label: str | None = None,
    action: str | None = None,
    outcome: str | None = None,
    attributes: dict | None = None,
    case_id: int = 1,
    source_type: CanonicalSourceType | None = None,
) -> CanonicalEvent:
    observed_at = BASE_TIME + timedelta(seconds=seconds) if seconds is not None else None
    ingested_at = BASE_TIME + timedelta(seconds=(seconds or 0) + 180)
    actor = (
        CanonicalEntity(
            id=f"ip:{actor_ip}",
            kind=EntityKind.IP_ADDRESS,
            ip=actor_ip,
        )
        if actor_ip
        else None
    )
    device = CanonicalEntity(id=device_id, kind=EntityKind.DEVICE)
    network = (
        CanonicalNetwork(
            source_ip=actor_ip,
            destination_ip="10.42.0.18",
            destination_port=554,
            protocol="tcp",
        )
        if actor_ip
        else None
    )
    return CanonicalEvent(
        event_id=UUID(int=index),
        case_id=case_id,
        observed_at=observed_at,
        ingested_at=ingested_at,
        event_type=event_type,
        source_label=source_label,
        device=device,
        actor=actor,
        target=device,
        network=network,
        action=action,
        outcome=outcome,
        attributes=attributes or {},
        provenance=CanonicalProvenance(
            evidence_id=UUID(int=10_000 + index),
            origin=origin,
            source_type=source_type or (
                CanonicalSourceType.LIVE_TELEMETRY
                if origin == EventOrigin.LIVE
                else CanonicalSourceType.SIMULATED
            ),
            source_name="golden-case",
            source_id="lab-collector" if origin == EventOrigin.LIVE else None,
            source_hash=f"{index:064x}"[-64:],
            source_record_reference=f"event:{index}",
            raw_record_hash=f"{index + 1:064x}"[-64:],
            adapter_name="golden",
            adapter_version="1.0",
        ),
    )


def golden_events() -> list[CanonicalEvent]:
    events = [
        canonical_event(
            1,
            seconds=0,
            event_type="network_flow",
            source_label="scanning",
        )
    ]
    events.extend(
        canonical_event(
            index,
            seconds=29 + index,
            event_type="authentication_failure",
            origin=EventOrigin.LIVE,
            action="authenticate",
            outcome="denied",
        )
        for index in range(2, 12)
    )
    for index, (seconds, temperature) in enumerate(
        ((60, 10), (70, 10), (80, 10), (90, 50)), start=12
    ):
        events.append(
            canonical_event(
                index,
                seconds=seconds,
                event_type="telemetry",
                origin=EventOrigin.LIVE,
                actor_ip=None,
                attributes={"temperature": temperature},
            )
        )
    events.append(
        canonical_event(
            16,
            seconds=None,
            event_type="network_flow",
            device_id="UNKNOWN-DEVICE",
            actor_ip=None,
            source_label="BenignTraffic",
        )
    )
    return events


def test_golden_hybrid_analysis_is_reproducible_and_explainable():
    events = golden_events()
    config = AnalysisConfig(critical_device_scores={"CAM-01": 90})
    service = AnalysisService(config)

    first = service.analyze(case_id=1, events=events)
    second = service.analyze(case_id=1, events=list(reversed(events)))

    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert first.input_event_count == first.analyzed_event_count == 16
    assert {finding.rule_id for finding in first.findings} == {
        "AUTH-001",
        "BASELINE-001",
        "LABEL-001",
    }
    assert len(first.alerts) == 2
    assert all(
        finding.live_detected
        for finding in first.findings
        if finding.rule_id in {"AUTH-001", "BASELINE-001"}
    )
    assert any(finding.rule_id == "LABEL-001" and not finding.live_detected for finding in first.findings)
    assert len(first.baselines) == 1
    assert first.baselines[0].threshold == 11.0
    assert first.correlations
    assert len(first.incidents) == 1
    assert first.incidents[0].maximum_risk == max(
        finding.risk.score for finding in first.findings
    )
    assert first.timeline[-1].entry_id == f"event:{UUID(int=16)}"
    assert first.timeline[-1].timestamp_basis == "unavailable"
    assert first.graph.nodes and first.graph.edges
    assert {point.series for point in first.chart_points} >= {
        "event_type",
        "origin",
        "finding_severity",
        "risk_band",
        "activity_minute",
    }
    for finding in first.findings:
        assert finding.condition_trace
        assert sum(factor.weighted_points for factor in finding.risk.factors) == finding.risk.score
        assert 0 <= finding.risk.score <= 100


def test_filters_are_stable_and_do_not_use_ingestion_as_observed_time():
    events = golden_events()
    event_filter = EventFilter(
        origins=["live"],
        event_types=["telemetry", "authentication_failure", "telemetry"],
        observed_from=BASE_TIME + timedelta(seconds=60),
        sort_direction=SortDirection.DESCENDING,
    )

    result = AnalysisService().analyze(
        case_id=1,
        events=list(reversed(events)),
        event_filter=event_filter,
    )

    assert result.analyzed_event_count == 4
    assert result.filter.event_types == ["authentication_failure", "telemetry"]
    observed = [
        next(event.observed_at for event in events if event.event_id == event_id)
        for event_id in result.event_ids
    ]
    assert observed == sorted(observed, reverse=True)
    assert all(timestamp is not None for timestamp in observed)


def test_batch_findings_do_not_create_live_alerts():
    event = canonical_event(
        101,
        seconds=0,
        event_type="network_flow",
        source_label="malicious",
    )

    result = AnalysisService().analyze(case_id=1, events=[event])

    assert len(result.findings) == 1
    assert result.findings[0].rule_id == "LABEL-001"
    assert result.alerts == []


def test_default_label_risk_has_a_versioned_repetition_reference():
    event = canonical_event(
        104,
        seconds=0,
        event_type="network_flow",
        source_label="malicious",
    )

    finding = AnalysisService().analyze(case_id=1, events=[event]).findings[0]
    repetition = next(factor for factor in finding.risk.factors if factor.name == "repetition")

    assert repetition.score == 25
    assert repetition.explanation == "1 occurrence(s) against configured reference 4"
    assert finding.risk.score == 59


def test_authentication_rule_requires_verified_actor_and_target_identities():
    missing_actors = [
        canonical_event(
            400 + index,
            seconds=index,
            event_type="authentication_failure",
            actor_ip=None,
            action="authenticate",
            outcome="denied",
        )
        for index in range(10)
    ]
    missing_targets = [
        canonical_event(
            500 + index,
            seconds=index,
            event_type="authentication_failure",
            action="authenticate",
            outcome="denied",
        ).model_copy(update={"device": None, "target": None})
        for index in range(10)
    ]

    for events in (missing_actors, missing_targets):
        result = AnalysisService().analyze(case_id=1, events=events)
        assert not any(finding.rule_id == "AUTH-001" for finding in result.findings)
        assert result.alerts == []


def test_authentication_rule_does_not_combine_distinct_known_actors():
    events = [
        canonical_event(
            600 + index,
            seconds=index,
            event_type="authentication_failure",
            actor_ip="185.77.12.44" if index < 5 else "203.0.113.9",
            action="authenticate",
            outcome="denied",
        )
        for index in range(10)
    ]

    result = AnalysisService().analyze(case_id=1, events=events)

    assert not any(finding.rule_id == "AUTH-001" for finding in result.findings)


def test_ciciot_dataset_labels_use_the_versioned_benign_set():
    attack = canonical_event(
        102,
        seconds=0,
        event_type="network_flow",
        source_label="DDoS-UDP_Flood",
        source_type=CanonicalSourceType.CICIOT2023_NETWORK,
    )
    benign = canonical_event(
        103,
        seconds=1,
        event_type="network_flow",
        source_label="BenignTraffic",
        source_type=CanonicalSourceType.CICIOT2023_NETWORK,
    )

    result = AnalysisService().analyze(case_id=1, events=[attack, benign])

    label_findings = [finding for finding in result.findings if finding.rule_id == "LABEL-001"]
    assert len(label_findings) == 1
    assert label_findings[0].trigger_event_ids == [UUID(int=102)]


def test_ton_iot_telemetry_uses_the_binary_dataset_label_rule():
    attack = canonical_event(
        105,
        seconds=0,
        event_type="telemetry",
        source_label="1",
        source_type=CanonicalSourceType.TON_IOT_TELEMETRY,
        attributes={"fridge_temperature": 21.4},
    )
    benign = canonical_event(
        106,
        seconds=1,
        event_type="telemetry",
        source_label="0",
        source_type=CanonicalSourceType.TON_IOT_TELEMETRY,
        attributes={"fridge_temperature": 13.1},
    )

    result = AnalysisService().analyze(case_id=1, events=[attack, benign])

    label_findings = [finding for finding in result.findings if finding.rule_id == "LABEL-001"]
    assert len(label_findings) == 1
    assert label_findings[0].trigger_event_ids == [UUID(int=105)]


def test_live_baseline_support_does_not_turn_a_batch_spike_into_a_live_alert():
    events = [
        canonical_event(
            110 + index,
            seconds=index * 10,
            event_type="telemetry",
            origin=EventOrigin.LIVE,
            actor_ip=None,
            attributes={"temperature": 10},
        )
        for index in range(3)
    ]
    events.append(
        canonical_event(
            120,
            seconds=40,
            event_type="telemetry",
            origin=EventOrigin.BATCH,
            actor_ip=None,
            attributes={"temperature": 50},
        )
    )

    result = AnalysisService().analyze(case_id=1, events=events)

    baseline_finding = next(
        finding for finding in result.findings if finding.rule_id == "BASELINE-001"
    )
    assert baseline_finding.live_detected is False
    assert baseline_finding.trigger_event_ids == [UUID(int=120)]
    assert result.alerts == []


def test_untimed_events_are_not_temporally_correlated():
    events = [
        canonical_event(201, seconds=None, event_type="status_change"),
        canonical_event(202, seconds=None, event_type="status_change"),
    ]

    result = AnalysisService().analyze(case_id=1, events=events)

    assert result.correlations == []
    assert all(entry.timestamp_basis == "unavailable" for entry in result.timeline)
    assert all(entry.occurred_at is None for entry in result.timeline)


def test_one_finding_remains_one_incident_without_temporal_edges():
    events = [
        canonical_event(
            210 + index,
            seconds=index * 200,
            event_type="telemetry",
            actor_ip=None,
            attributes={"temperature": value},
        )
        for index, value in enumerate((10, 10, 10, 50))
    ]

    result = AnalysisService().analyze(case_id=1, events=events)

    assert result.correlations == []
    assert len(result.findings) == 1
    assert len(result.incidents) == 1
    assert set(result.incidents[0].event_ids) == {event.event_id for event in events}
    assert result.incidents[0].correlation_edge_ids == []


def test_equal_entity_text_with_different_kinds_does_not_correlate():
    left = canonical_event(
        220,
        seconds=0,
        event_type="status_change",
        device_id="DEVICE-A",
        actor_ip=None,
    ).model_copy(
        update={
            "actor": CanonicalEntity(id="shared", kind=EntityKind.USER),
            "network": None,
        }
    )
    right = canonical_event(
        221,
        seconds=1,
        event_type="status_change",
        device_id="DEVICE-B",
        actor_ip=None,
    ).model_copy(
        update={
            "actor": CanonicalEntity(id="shared", kind=EntityKind.SERVICE),
            "network": None,
        }
    )

    result = AnalysisService().analyze(case_id=1, events=[left, right])

    assert result.correlations == []


def test_analysis_rejects_cross_case_and_duplicate_event_inputs():
    event = canonical_event(301, seconds=0, event_type="status_change")
    wrong_case = canonical_event(302, seconds=0, event_type="status_change", case_id=2)
    service = AnalysisService()

    with pytest.raises(ValueError, match="requested case"):
        service.analyze(case_id=1, events=[event, wrong_case])
    with pytest.raises(ValueError, match="unique"):
        service.analyze(case_id=1, events=[event, event])


def test_risk_configuration_is_bounded_and_requires_exact_weight_total():
    with pytest.raises(ValidationError):
        RiskWeights(severity=50)
    with pytest.raises(ValidationError):
        AnalysisConfig(critical_device_scores={"CAM-01": 101})
