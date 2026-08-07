# Canonical Event Contract

Step 4 maps validated batch records and accepted live telemetry into the same strict `CanonicalEvent` schema. The contract is version `1.0`; Python remains the only authority for normalization decisions.

## Core shape

```json
{
  "schema_version": "1.0",
  "event_id": "deterministic-uuid",
  "case_id": 1,
  "observed_at": "2026-08-06T05:00:00Z",
  "ingested_at": "2026-08-06T05:00:02Z",
  "event_type": "authentication_failure",
  "source_event_type": "Authentication Failure",
  "source_label": null,
  "device": {
    "id": "camera-1",
    "kind": "device",
    "device_type": "smart_camera"
  },
  "actor": {
    "id": "ip:203.0.113.8",
    "kind": "ip_address",
    "ip": "203.0.113.8"
  },
  "target": {
    "id": "camera-1",
    "kind": "device"
  },
  "network": {
    "source_ip": "203.0.113.8",
    "destination_ip": "192.0.2.20",
    "destination_port": 443,
    "protocol": "tcp"
  },
  "action": null,
  "outcome": "denied",
  "attributes": {
    "attempts": 14
  },
  "provenance": {
    "evidence_id": "evidence-uuid",
    "origin": "batch",
    "source_type": "simulated",
    "source_name": "evidence.csv",
    "source_id": null,
    "source_hash": "sha256-of-original-evidence",
    "source_record_reference": "row:7",
    "raw_record_hash": "sha256-of-the-source-record",
    "adapter_name": "simulated",
    "adapter_version": "1.0",
    "normalization_version": "1.0"
  },
  "normalization_warnings": []
}
```

Risk, severity, alerts, correlation conclusions, and AI narrative are deliberately absent. They are derived later and must reference canonical event identifiers.

## Source mappings

| Source | Observed time | Event type | Identity policy | Source label |
| --- | --- | --- | --- | --- |
| Simulated | `timestamp` | normalized source `event_type` | required `device_id`; optional device/IP/MAC fields | `label` or `type` when present |
| TON_IoT network | `ts` | `network_flow` | source/destination IP entities; device exists only when the source supplies a trusted `device_id` | required original `label`; original `type` is retained separately |
| CICIoT2023 network | optional `timestamp`, `ts`, or `time` | `network_flow` | destination IP remains a network target; device remains absent unless the source supplies an identity | required original `label` |
| Generic upload | optional common timestamp and identity aliases | normalized source type or `generic_event` | missing identity is preserved as a warning | original `label` when present |
| Live telemetry | validated `observed_at` | validated live `event_type` | validated `device_id` and `source_id` | none |

An IP address is not promoted to a device identity merely because it is the flow destination. Missing device identity is retained as `DEVICE_ID_UNAVAILABLE`. Likewise, live `event_type` is not copied into `action`; `action` remains null unless the source contract provides an independent action value.

## Determinism and time

Event IDs are UUIDv5 values derived from the case, evidence identifier, source-record reference, adapter/version, and deterministic raw-record hash. Reprocessing identical evidence with the same configuration produces the same identifier.

All canonical timestamps are UTC. Numeric source timestamps are interpreted as Unix seconds, milliseconds, or microseconds according to magnitude. Timezone-aware ISO timestamps are converted to UTC. A timezone-naive timestamp is explicitly interpreted as UTC with an `ASSUMED_UTC` warning. If a source such as a processed CICIoT2023 feature table has no observed time, `observed_at` stays null; ingestion time is never substituted for evidence time.

## Attributes and provenance

Flat source fields not mapped into common fields remain in `attributes`. CSV strings are conservatively typed as booleans, integers, or finite floating-point values only when unambiguous; padded identifiers such as `001` remain strings. Unsupported nested or non-finite values are omitted with warnings.

Every event retains evidence ID, original evidence hash, logical row/sequence reference, deterministic raw-record hash, source type/name/ID, batch/live origin, adapter version, and normalization version. Batch normalization accepts only a `ValidatedBatchRecord` issued by Step 3, verifies its metadata, and recomputes its row hash before mapping. Source fields that collapse to the same normalized name, such as `src-ip` and `src_ip`, are rejected as ambiguous instead of selecting one value. The original evidence remains the authority for full raw-record review.

The current TON_IoT and CICIoT2023 adapters are pinned to the versioned Step 3 profile fixtures. The exact selected dataset release must match those headers or receive a new versioned profile and adapter rather than an undocumented mapping change.
