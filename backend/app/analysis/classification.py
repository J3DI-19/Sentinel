from __future__ import annotations

from dataclasses import dataclass

from app.analysis.schemas import ClassificationSource, FindingClassification, Severity


@dataclass(frozen=True)
class TaxonomyEntry:
    category: str
    subcategory: str
    display_name: str
    severity: Severity


_TAXONOMY: dict[str, TaxonomyEntry] = {
    "backdoor": TaxonomyEntry("persistence", "backdoor", "Backdoor", Severity.HIGH),
    "botnet": TaxonomyEntry("malware", "botnet", "Botnet", Severity.CRITICAL),
    "brute force": TaxonomyEntry("credential_attack", "brute_force", "Brute force", Severity.HIGH),
    "ddos": TaxonomyEntry("denial_of_service", "distributed_denial_of_service", "DDoS", Severity.CRITICAL),
    "dos": TaxonomyEntry("denial_of_service", "denial_of_service", "DoS", Severity.CRITICAL),
    "exploit": TaxonomyEntry("exploitation", "exploit", "Exploit", Severity.HIGH),
    "injection": TaxonomyEntry("exploitation", "injection", "Injection", Severity.HIGH),
    "password": TaxonomyEntry("credential_attack", "password_attack", "Password attack", Severity.HIGH),
    "probe": TaxonomyEntry("discovery", "probing", "Probing", Severity.MEDIUM),
    "ransomware": TaxonomyEntry("malware", "ransomware", "Ransomware", Severity.CRITICAL),
    "recon": TaxonomyEntry("discovery", "reconnaissance", "Reconnaissance", Severity.MEDIUM),
    "scanning": TaxonomyEntry("discovery", "scanning", "Scanning", Severity.MEDIUM),
    "xss": TaxonomyEntry("exploitation", "cross_site_scripting", "Cross-site scripting", Severity.HIGH),
}

_ALIASES = {
    "back-door": "backdoor",
    "bruteforce": "brute force",
    "distributed denial of service": "ddos",
    "password attack": "password",
    "ransom ware": "ransomware",
    "scan": "scanning",
}


def dataset_classification(value: str, confidence: int = 95) -> tuple[FindingClassification, Severity]:
    normalized = " ".join(value.strip().casefold().replace("_", " ").split())
    canonical = _ALIASES.get(normalized, normalized)
    entry = _TAXONOMY.get(canonical)
    if entry is None:
        entry = TaxonomyEntry("unknown", "malicious", value.strip() or "Malicious", Severity.HIGH)
        confidence = min(confidence, 60)
    return FindingClassification(
        category=entry.category,
        subcategory=entry.subcategory,
        display_name=entry.display_name,
        source=ClassificationSource.DATASET_LABEL,
        source_field="attributes.attack_type",
        source_value=value,
        confidence=confidence,
        tags=sorted({entry.category, entry.subcategory}),
    ), entry.severity


def rule_classification(rule_id: str, source_value: str) -> FindingClassification:
    values = {
        "RATE-001": ("availability", "excessive_request_rate", "Excessive request rate", ClassificationSource.DETERMINISTIC_RULE, 90),
        "AUTH-001": ("credential_attack", "repeated_authentication_failure", "Repeated authentication failures", ClassificationSource.DETERMINISTIC_RULE, 98),
        "BASELINE-001": ("anomaly", "telemetry_baseline_deviation", "Telemetry baseline anomaly", ClassificationSource.BEHAVIORAL_ANOMALY, 80),
        "TELEMETRY-ROC-001": ("telemetry_anomaly", "rapid_change", "Rapid telemetry change", ClassificationSource.BEHAVIORAL_ANOMALY, 82),
        "NET-FANOUT-001": ("network_anomaly", "destination_fan_out", "Unusual destination fan-out", ClassificationSource.BEHAVIORAL_ANOMALY, 85),
        "NET-PORTSCAN-001": ("discovery_anomaly", "port_scan", "Unusual destination-port fan-out", ClassificationSource.BEHAVIORAL_ANOMALY, 88),
        "NET-FAILURE-001": ("network_anomaly", "connection_failure_burst", "Connection failure burst", ClassificationSource.DETERMINISTIC_RULE, 90),
    }
    category, subcategory, display, source, confidence = values[rule_id]
    return FindingClassification(
        category=category,
        subcategory=subcategory,
        display_name=display,
        source=source,
        source_field="condition_trace",
        source_value=source_value,
        confidence=confidence,
        tags=sorted({category, subcategory}),
    )
