from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.analysis.config import AnalysisConfig, RiskWeights
from app.analysis.correlation import build_incidents
from app.analysis.schemas import (
    INCIDENT_CORRELATION_EDGE_REFERENCE_LIMIT,
    INCIDENT_FINDING_REFERENCE_LIMIT,
    EventFilter,
    Severity,
    SortDirection,
)
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
    assert finding.risk.base_score == 59
    assert finding.risk.score == 49
    assert finding.risk.penalties[0].reason == "generic_unverified_label"


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


def test_dataset_label_findings_group_shared_attack_classes_and_vary_severity():
    evidence_id = UUID(int=20_000)
    events = [
        canonical_event(
            130 + index,
            seconds=index,
            event_type="telemetry",
            source_label="1",
            source_type=CanonicalSourceType.TON_IOT_FRIDGE_TELEMETRY,
            attributes={"attack_type": attack_class},
        )
        for index, attack_class in enumerate(("scanning", "scanning", "ransomware"))
    ]
    events = [
        event.model_copy(
            update={
                "provenance": event.provenance.model_copy(
                    update={"evidence_id": evidence_id}
                )
            }
        )
        for event in events
    ]

    result = AnalysisService().analyze(case_id=1, events=events)

    label_findings = [finding for finding in result.findings if finding.rule_id == "LABEL-001"]
    assert len(label_findings) == 2
    by_title = {finding.title: finding for finding in label_findings}
    assert by_title["Dataset-labelled Scanning activity"].severity.value == "medium"
    assert len(by_title["Dataset-labelled Scanning activity"].event_ids) == 2
    assert by_title["Dataset-labelled Ransomware activity"].severity.value == "critical"
    assert by_title["Dataset-labelled Ransomware activity"].classification.source.value == "dataset_label"
    assert {point.category for point in result.chart_points if point.series == "attack_class"} == {
        "ransomware",
        "scanning",
    }


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
    assert result.incidents[0].correlation_edge_count == 0
    assert result.incidents[0].correlation_edges_truncated is False


def test_dense_incident_bounds_correlation_references_without_losing_total():
    events = [
        canonical_event(
            1_000 + index,
            seconds=index,
            event_type="network_flow",
            source_label="malicious",
        )
        for index in range(100)
    ]

    first = AnalysisService().analyze(case_id=1, events=events)
    second = AnalysisService().analyze(case_id=1, events=list(reversed(events)))

    assert len(first.correlations) > INCIDENT_CORRELATION_EDGE_REFERENCE_LIMIT
    assert len(first.incidents) == 1
    incident = first.incidents[0]
    assert len(incident.correlation_edge_ids) == INCIDENT_CORRELATION_EDGE_REFERENCE_LIMIT
    assert incident.correlation_edge_count == len(first.correlations)
    assert incident.correlation_edges_truncated is True
    assert incident.correlation_edge_ids == second.incidents[0].correlation_edge_ids
    assert first.configuration.incident_reference_policy_version == "1.0"


def test_dense_incident_bounds_finding_references_without_losing_total():
    event = canonical_event(
        50_000,
        seconds=0,
        event_type="telemetry",
        source_label="1",
        source_type=CanonicalSourceType.TON_IOT_FRIDGE_TELEMETRY,
        attributes={"attack_type": "ddos"},
    )
    template = AnalysisService().analyze(case_id=1, events=[event]).findings[0]
    total = INCIDENT_FINDING_REFERENCE_LIMIT + 520
    findings = [
        template.model_copy(update={"finding_id": UUID(int=index + 1)})
        for index in range(total)
    ]

    first = build_incidents(
        case_id=1,
        events=[event],
        findings=findings,
        alerts=[],
        correlations=[],
    )[0]
    second = build_incidents(
        case_id=1,
        events=[event],
        findings=list(reversed(findings)),
        alerts=[],
        correlations=[],
    )[0]

    assert len(first.finding_ids) == INCIDENT_FINDING_REFERENCE_LIMIT
    assert first.finding_count == total
    assert first.finding_ids_truncated is True
    assert first.finding_ids == second.finding_ids


def test_transitive_activity_is_split_into_bounded_incident_sessions():
    events = [
        canonical_event(
            60_000 + index,
            seconds=index * 60,
            event_type="network_flow",
            source_label="malicious",
        )
        for index in range(11)
    ]

    result = AnalysisService().analyze(case_id=1, events=events)

    assert len(result.incidents) == 4
    assert all(
        (incident.ended_at - incident.started_at).total_seconds()
        <= incident.maximum_trigger_span_seconds
        for incident in result.incidents
    )
    assert all(
        incident.grouping_policy == "finding_centered_bounded_session"
        for incident in result.incidents
    )


def test_dataset_label_findings_are_split_by_time_and_record_bounds():
    evidence_id = UUID(int=88_000)
    events = [
        canonical_event(
            61_000 + index,
            seconds=index * 60,
            event_type="network_flow",
            source_label="malicious",
        ).model_copy(
            update={
                "provenance": canonical_event(
                    61_000 + index,
                    seconds=index * 60,
                    event_type="network_flow",
                    source_label="malicious",
                ).provenance.model_copy(update={"evidence_id": evidence_id})
            }
        )
        for index in range(11)
    ]

    result = AnalysisService().analyze(case_id=1, events=events)
    label_findings = [
        finding for finding in result.findings if finding.rule_id == "LABEL-001"
    ]

    assert len(label_findings) == 4
    assert max(len(finding.event_ids) for finding in label_findings) == 3
    assert all("bounded temporal session" in finding.summary for finding in label_findings)


def test_incident_does_not_absorb_correlated_events_without_findings():
    finding_event = canonical_event(
        62_000,
        seconds=0,
        event_type="network_flow",
        source_label="malicious",
    )
    background = [
        canonical_event(
            62_000 + index,
            seconds=index * 60,
            event_type="network_flow",
        )
        for index in range(1, 8)
    ]

    result = AnalysisService().analyze(
        case_id=1,
        events=[finding_event, *background],
    )

    assert len(result.incidents) == 1
    assert result.incidents[0].event_ids == [finding_event.event_id]


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
    with pytest.raises(ValidationError, match="incident_max_trigger_span_seconds"):
        AnalysisConfig(incident_max_trigger_span_seconds=119)


def test_dataset_ddos_classification_is_explicitly_source_supplied():
    event = canonical_event(
        900,
        seconds=0,
        event_type="telemetry",
        source_label="1",
        source_type=CanonicalSourceType.TON_IOT_FRIDGE_TELEMETRY,
        attributes={"attack_type": "ddos"},
    )
    finding = AnalysisService().analyze(case_id=1, events=[event]).findings[0]
    assert finding.title == "Dataset-labelled DDoS activity"
    assert finding.classification.category == "denial_of_service"
    assert finding.classification.subcategory == "distributed_denial_of_service"
    assert finding.classification.source.value == "dataset_label"
    assert finding.classification.source_field == "attributes.attack_type"
    assert finding.classification.source_value == "ddos"
    assert finding.classification.tags == ["denial_of_service", "distributed_denial_of_service"]


def test_activity_windows_explain_source_labels_and_preserve_unknown_cause():
    classified = canonical_event(
        901, seconds=0, event_type="telemetry", source_label="1",
        source_type=CanonicalSourceType.TON_IOT_FRIDGE_TELEMETRY,
        attributes={"attack_type": "ddos"},
    )
    unexplained = canonical_event(902, seconds=60, event_type="device_state")
    result = AnalysisService().analyze(case_id=1, events=[classified, unexplained])
    assert result.activity_windows[0].cause_status == "source_classified"
    assert result.activity_windows[0].source_classifications[0].value == "ddos"
    assert result.activity_windows[1].cause_status == "undetermined"
    assert "No source classification" in result.activity_windows[1].explanation


def test_incident_exposes_peak_severity_and_summary_metrics():
    events = [
        canonical_event(
            910 + index, seconds=index, event_type="telemetry", source_label="1",
            source_type=CanonicalSourceType.TON_IOT_FRIDGE_TELEMETRY,
            attributes={"attack_type": attack},
        )
        for index, attack in enumerate(("scanning", "ransomware"))
    ]
    incident = AnalysisService().analyze(case_id=1, events=events).incidents[0]
    assert incident.severity.value == "critical"
    assert incident.severity_counts[Severity.CRITICAL] == 1
    assert incident.severity_counts[Severity.MEDIUM] == 1
    assert incident.evidence_count == 2
    assert incident.entity_count >= 1
    assert "ransomware" in incident.tags


def test_blind_network_rules_detect_behavior_without_source_labels():
    events = []
    for index in range(6):
        event = canonical_event(
            1000 + index, seconds=index, event_type="network_flow", device_id="camera-01",
            source_type=CanonicalSourceType.IOT23_ZEEK_BLIND, source_label=None,
        )
        events.append(event.model_copy(update={"network": event.network.model_copy(update={"destination_ip": f"10.0.1.{index + 1}", "destination_port": 1000 + index})}))

    result = AnalysisService(AnalysisConfig(network_fanout_threshold=5, network_port_scan_threshold=5)).analyze(case_id=1, events=events)
    rules = {finding.rule_id for finding in result.findings}

    assert {"NET-FANOUT-001", "NET-PORTSCAN-001"} <= rules
    assert all(finding.classification.source.value != "dataset_label" for finding in result.findings)
    assert all(finding.classification.source_field == "condition_trace" for finding in result.findings)


def test_hai_and_iot23_findings_converge_by_device_and_overlapping_time():
    telemetry = [
        canonical_event(1100 + index, seconds=index * 5, event_type="telemetry", device_id="edge-device-01", actor_ip=None, source_type=CanonicalSourceType.HAI_ICS_BLIND, attributes={"pressure": value})
        for index, value in enumerate((10, 10, 10, 60))
    ]
    flows = []
    for index in range(4):
        event = canonical_event(1200 + index, seconds=16 + index, event_type="network_flow", device_id="edge-device-01", source_type=CanonicalSourceType.IOT23_ZEEK_BLIND)
        flows.append(event.model_copy(update={"network": event.network.model_copy(update={"destination_ip": f"10.0.2.{index + 1}", "destination_port": 2000 + index})}))
    result = AnalysisService(AnalysisConfig(network_fanout_threshold=4, network_port_scan_threshold=4)).analyze(case_id=1, events=[*telemetry, *flows])

    assert {"BASELINE-001", "NET-FANOUT-001", "NET-PORTSCAN-001"} <= {finding.rule_id for finding in result.findings}
    assert len(result.incidents) == 1
    assert result.incidents[0].entity_count >= 1
    assert result.incidents[0].evidence_count >= 2
