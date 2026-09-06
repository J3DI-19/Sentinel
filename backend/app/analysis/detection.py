from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from statistics import fmean, pstdev
from uuid import UUID

from app.analysis.config import AnalysisConfig
from app.analysis.helpers import primary_entity_id, stable_uuid, unique_sorted_uuids
from app.analysis.schemas import BaselineSummary, ConditionTrace, Severity
from app.normalization.schemas import CanonicalEvent, CanonicalSourceType, EventOrigin


@dataclass(frozen=True)
class DetectionCandidate:
    rule_id: str
    title: str
    summary: str
    severity: Severity
    confidence: int
    event_ids: tuple[UUID, ...]
    trigger_event_ids: tuple[UUID, ...]
    evidence_ids: tuple[UUID, ...]
    condition_trace: tuple[ConditionTrace, ...]
    entity_id: str | None
    repetition_count: int
    repetition_reference: int
    live_detected: bool


def detect(
    events: list[CanonicalEvent], config: AnalysisConfig
) -> tuple[list[DetectionCandidate], list[BaselineSummary]]:
    by_id = {event.event_id: event for event in events}
    candidates = [
        *_detect_malicious_labels(events, config),
        *_detect_request_rate(events, config),
        *_detect_authentication_failures(events, config),
    ]
    baseline_candidates, baselines = _detect_baseline_spikes(events, config)
    candidates.extend(baseline_candidates)
    candidates.sort(
        key=lambda candidate: (
            candidate.rule_id,
            tuple(str(value) for value in candidate.event_ids),
        )
    )
    for candidate in candidates:
        if any(event_id not in by_id for event_id in candidate.event_ids):
            raise ValueError("detection candidate references an unknown event")
    return candidates, baselines


def _candidate(
    *,
    rule_id: str,
    title: str,
    summary: str,
    severity: Severity,
    confidence: int,
    events: list[CanonicalEvent],
    trigger_events: list[CanonicalEvent] | None = None,
    trace: list[ConditionTrace],
    entity_id: str | None,
    repetition_reference: int,
    repetition_count: int = 1,
) -> DetectionCandidate:
    ordered = sorted(events, key=lambda event: str(event.event_id))
    triggers = sorted(trigger_events or events, key=lambda event: str(event.event_id))
    if not {event.event_id for event in triggers} <= {event.event_id for event in ordered}:
        raise ValueError("trigger events must be included in supporting events")
    return DetectionCandidate(
        rule_id=rule_id,
        title=title,
        summary=summary,
        severity=severity,
        confidence=confidence,
        event_ids=tuple(event.event_id for event in ordered),
        trigger_event_ids=tuple(event.event_id for event in triggers),
        evidence_ids=tuple(
            unique_sorted_uuids(event.provenance.evidence_id for event in ordered)
        ),
        condition_trace=tuple(trace),
        entity_id=entity_id,
        repetition_count=repetition_count,
        repetition_reference=repetition_reference,
        live_detected=any(event.provenance.origin == EventOrigin.LIVE for event in triggers),
    )


def _detect_malicious_labels(
    events: list[CanonicalEvent], config: AnalysisConfig
) -> list[DetectionCandidate]:
    labels = {label.casefold() for label in config.malicious_labels}
    benign_labels = {label.casefold() for label in config.dataset_benign_labels}
    matched_events: dict[tuple[str, str, str, str], list[tuple[CanonicalEvent, str, str]]] = {}
    for event in events:
        label = (event.source_label or "").strip().casefold()
        if event.provenance.source_type in {
            CanonicalSourceType.TON_IOT_NETWORK,
            CanonicalSourceType.TON_IOT_FRIDGE_TELEMETRY,
        }:
            matched = label == "1"
            expected = "TON_IoT binary label equals 1"
        elif event.provenance.source_type == CanonicalSourceType.CICIOT2023_NETWORK:
            matched = bool(label) and label not in benign_labels
            expected = "CICIoT2023 label is not in the configured benign-label set"
        else:
            matched = label in labels
            expected = "Source label is in the configured malicious-label set"
        if not matched:
            continue
        attack_class = _attack_class(event)
        entity_id = primary_entity_id(event) or "unknown-entity"
        evidence_id = str(event.provenance.evidence_id)
        key = (event.provenance.source_type.value, evidence_id, entity_id, attack_class)
        matched_events.setdefault(key, []).append((event, expected, label))

    findings: list[DetectionCandidate] = []
    for (_, _, entity_id, attack_class), matches in sorted(matched_events.items()):
        grouped = [event for event, _, _ in matches]
        expected = matches[0][1]
        actual_labels = sorted({actual for _, _, actual in matches})
        severity = _dataset_attack_severity(attack_class)
        findings.append(
            _candidate(
                rule_id="LABEL-001",
                title=f"Dataset identifies {attack_class} activity",
                summary=(
                    f"{len(grouped)} source records for {entity_id} were grouped by the "
                    f"persisted attack class {attack_class!r} and matched the versioned "
                    "malicious-label rule."
                ),
                severity=severity,
                confidence=95,
                events=grouped,
                trace=[
                    ConditionTrace(
                        condition=expected,
                        field="source_label",
                        operator="in",
                        expected=(
                            ",".join(sorted(benign_labels))
                            if event.provenance.source_type
                            == CanonicalSourceType.CICIOT2023_NETWORK
                            else "1"
                            if event.provenance.source_type
                            in {
                                CanonicalSourceType.TON_IOT_NETWORK,
                                CanonicalSourceType.TON_IOT_FRIDGE_TELEMETRY,
                            }
                            else ",".join(sorted(labels))
                        ),
                        actual=",".join(actual_labels),
                        matched=True,
                    ),
                    ConditionTrace(
                        condition="Records share a normalized source attack class",
                        field="attributes.attack_type",
                        operator="equals",
                        expected=attack_class,
                        actual=attack_class,
                        matched=True,
                    ),
                ],
                entity_id=None if entity_id == "unknown-entity" else entity_id,
                repetition_reference=config.label_repetition_reference,
                repetition_count=len(grouped),
            )
        )
    return findings


def _attack_class(event: CanonicalEvent) -> str:
    """Return the most specific persisted source classification available."""
    for value in (
        event.attributes.get("attack_type"),
        event.source_event_type,
        event.source_label,
    ):
        if isinstance(value, str) and value.strip():
            return value.strip().casefold().replace("_", " ")
    return "malicious"


def _dataset_attack_severity(attack_class: str) -> Severity:
    """Classify source-labelled activity without pretending every class is equal."""
    normalized = attack_class.casefold()
    if any(token in normalized for token in ("ransom", "ddos", "dos", "botnet")):
        return Severity.CRITICAL
    if any(token in normalized for token in ("backdoor", "inject", "password", "brute", "exploit")):
        return Severity.HIGH
    if any(token in normalized for token in ("scan", "recon", "probe")):
        return Severity.MEDIUM
    return Severity.HIGH


def _detect_request_rate(
    events: list[CanonicalEvent], config: AnalysisConfig
) -> list[DetectionCandidate]:
    findings: list[DetectionCandidate] = []
    for event in events:
        request_count = _numeric(event.attributes.get("requests"))
        baseline = _numeric(event.attributes.get("baseline"))
        if request_count is None or baseline is None or baseline <= 0:
            continue
        threshold = baseline * config.request_rate_multiplier
        if request_count < threshold:
            continue
        findings.append(
            _candidate(
                rule_id="RATE-001",
                title="Request rate exceeds the declared baseline",
                summary=(
                    f"Observed request count {request_count:g} met the deterministic "
                    f"threshold {threshold:g}."
                ),
                severity=Severity.HIGH,
                confidence=90,
                events=[event],
                trace=[
                    ConditionTrace(
                        condition="Requests meet or exceed baseline multiplier",
                        field="attributes.requests",
                        operator=">=",
                        expected=f"{threshold:g}",
                        actual=f"{request_count:g}",
                        matched=True,
                    )
                ],
                entity_id=primary_entity_id(event),
                repetition_reference=config.request_rate_repetition_reference,
            )
        )
    return findings


def _detect_authentication_failures(
    events: list[CanonicalEvent], config: AnalysisConfig
) -> list[DetectionCandidate]:
    groups: dict[tuple[str, str, str, str], list[CanonicalEvent]] = {}
    for event in events:
        if event.observed_at is None or not _is_authentication_failure(event):
            continue
        entity = event.device or event.target
        actor = event.actor
        if entity is None or actor is None:
            continue
        groups.setdefault(
            (entity.kind.value, entity.id, actor.kind.value, actor.id), []
        ).append(event)

    findings: list[DetectionCandidate] = []
    window = timedelta(seconds=config.authentication_window_seconds)
    for (_, entity_id, _, actor_id), group in sorted(groups.items()):
        group.sort(key=lambda event: (event.observed_at, str(event.event_id)))
        active: list[CanonicalEvent] = []
        last_trigger = None
        for event in group:
            active = [
                candidate
                for candidate in active
                if event.observed_at - candidate.observed_at <= window
            ]
            active.append(event)
            if len(active) < config.authentication_failure_threshold:
                continue
            if last_trigger is not None and event.observed_at - last_trigger <= window:
                continue
            contributing = active[-config.authentication_failure_threshold :]
            span = (contributing[-1].observed_at - contributing[0].observed_at).total_seconds()
            findings.append(
                _candidate(
                    rule_id="AUTH-001",
                    title="Repeated authentication failures",
                    summary=(
                        f"{len(contributing)} authentication failures for {entity_id} from "
                        f"{actor_id} occurred within {span:g} seconds."
                    ),
                    severity=Severity.CRITICAL,
                    confidence=98,
                    events=contributing,
                    trigger_events=[event],
                    trace=[
                        ConditionTrace(
                            condition="Authentication failure count reaches threshold",
                            field="event_count",
                            operator=">=",
                            expected=str(config.authentication_failure_threshold),
                            actual=str(len(contributing)),
                            matched=True,
                        ),
                        ConditionTrace(
                            condition="Failures occur inside the configured time window",
                            field="observed_at",
                            operator="span<=",
                            expected=str(config.authentication_window_seconds),
                            actual=f"{span:g}",
                            matched=True,
                        ),
                        ConditionTrace(
                            condition="Actor identity is stable across contributing events",
                            field="actor.id",
                            operator="equals",
                            expected=actor_id,
                            actual=actor_id,
                            matched=True,
                        ),
                    ],
                    entity_id=entity_id,
                    repetition_count=len(contributing),
                    repetition_reference=config.authentication_failure_threshold,
                )
            )
            last_trigger = event.observed_at
    return findings


def _detect_baseline_spikes(
    events: list[CanonicalEvent], config: AnalysisConfig
) -> tuple[list[DetectionCandidate], list[BaselineSummary]]:
    streams: dict[tuple[str, str], list[tuple[CanonicalEvent, float]]] = {}
    for event in events:
        if event.observed_at is None or event.event_type != "telemetry":
            continue
        entity_id = primary_entity_id(event)
        if entity_id is None:
            continue
        for metric, raw_value in event.attributes.items():
            value = _numeric(raw_value)
            if value is not None and metric != "sequence":
                streams.setdefault((entity_id, metric), []).append((event, value))

    findings: list[DetectionCandidate] = []
    baselines: list[BaselineSummary] = []
    for (entity_id, metric), samples in sorted(streams.items()):
        samples.sort(key=lambda item: (item[0].observed_at, str(item[0].event_id)))
        for index in range(config.baseline_min_samples, len(samples)):
            history = samples[max(0, index - config.baseline_max_samples) : index]
            current_event, current_value = samples[index]
            values = [value for _, value in history]
            mean = fmean(values)
            deviation = pstdev(values)
            threshold = mean + max(
                config.baseline_minimum_delta,
                config.baseline_sigma * deviation,
            )
            sample_ids = [event.event_id for event, _ in history]
            baseline = BaselineSummary(
                baseline_id=stable_uuid(
                    "baseline", entity_id, metric, *(str(value) for value in sample_ids), current_event.event_id
                ),
                entity_id=entity_id,
                metric=metric,
                sample_event_ids=sample_ids,
                sample_count=len(history),
                mean=round(mean, 6),
                population_stddev=round(deviation, 6),
                threshold=round(threshold, 6),
                evaluated_event_id=current_event.event_id,
                window_start=history[0][0].observed_at,
                window_end=history[-1][0].observed_at,
            )
            baselines.append(baseline)
            if current_value <= threshold:
                continue
            supporting = [event for event, _ in history] + [current_event]
            findings.append(
                _candidate(
                    rule_id="BASELINE-001",
                    title="Telemetry metric exceeds its behavioural baseline",
                    summary=(
                        f"{metric} value {current_value:g} for {entity_id} exceeded the "
                        f"deterministic baseline threshold {threshold:g}."
                    ),
                    severity=Severity.HIGH,
                    confidence=80,
                    events=supporting,
                    trigger_events=[current_event],
                    trace=[
                        ConditionTrace(
                            condition="A minimum baseline sample is available",
                            field="baseline.sample_count",
                            operator=">=",
                            expected=str(config.baseline_min_samples),
                            actual=str(len(history)),
                            matched=True,
                        ),
                        ConditionTrace(
                            condition="Current metric exceeds mean plus configured deviation",
                            field=f"attributes.{metric}",
                            operator=">",
                            expected=f"{threshold:g}",
                            actual=f"{current_value:g}",
                            matched=True,
                        ),
                    ],
                    entity_id=entity_id,
                    repetition_count=1,
                    repetition_reference=config.baseline_repetition_reference,
                )
            )
    baselines.sort(key=lambda baseline: str(baseline.baseline_id))
    return findings, baselines


def _is_authentication_failure(event: CanonicalEvent) -> bool:
    if event.event_type in {"authentication_failure", "login_failure"}:
        return True
    return event.action == "authenticate" and event.outcome in {
        "denied",
        "failure",
        "failed",
    }


def _numeric(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)
