# Evidence Validation Contract

Step 3 validates evidence before canonical normalization or deterministic analysis. It does not create canonical events, alerts, scores, correlations, or API routes.

## Batch evidence

The backend accepts original evidence bytes together with a filename, source profile, optional case identifier, and optional media type. CSV and JSON are supported. JSON must be either a list of record objects or an object with a `records` list.

Every attempt produces an `EvidenceValidationReport` containing:

- a generated evidence identifier;
- the SHA-256 hash of the unmodified bytes;
- original and sanitized filenames;
- byte size, media type, source profile, validator version, and UTC receipt time;
- `accepted`, `accepted_with_warnings`, or `rejected` status;
- total, accepted, and rejected record counts;
- structured file-, column-, and row-level issues.

Invalid data is never silently repaired. A mixed file may be accepted with warnings when at least one record is valid. A file-level failure, a missing required column, or a file with no valid records is rejected.

`validate_with_records` is the Step 3-to-Step 4 boundary. In addition to the report, it returns a `ValidatedBatchRecord` for each accepted row and never returns rejected rows. Each handoff contains the evidence ID, source type, dataset profile, validator version, original row number, parsed record, and a deterministic SHA-256 record hash. Step 4 verifies all of those values against the evidence metadata and recomputes the record hash before normalization; callers cannot bypass Step 3 by supplying an arbitrary row dictionary.

## Versioned profiles

| Profile | Minimal required columns |
| --- | --- |
| `simulated@1.0` | `timestamp`, `device_id`, `event_type` |
| `ton_iot_network@1.0` | `ts`, `src_ip`, `dst_ip`, `label` |
| `ciciot2023_network@1.0` | `flow_duration`, `Protocol Type`, `label` |
| `generic@1.0` | No dataset-specific columns; structural checks still apply |

The TON_IoT profile intentionally names the network subset because TON_IoT contains heterogeneous sources. Additional TON_IoT subsets must receive separate profiles instead of weakening this contract. Small synthetic contract fixtures preserve the expected headers without redistributing dataset records; they must be compared with the exact selected dataset release before an adapter is finalized in Step 4.

Generic validation has no dataset-specific required columns, but Step 4 still rejects a row that cannot produce any meaningful canonical time, type, identity, label, or attribute.

## Live telemetry handoff

The transport-neutral `LiveTelemetryInput` contract is version `1.0`. The live-collection phase may carry it over HTTP or MQTT without changing its forensic meaning.

Required fields are:

```json
{
  "schema_version": "1.0",
  "case_id": 1,
  "source_id": "arduino-lab-1",
  "device_id": "door-sensor-1",
  "event_type": "telemetry",
  "observed_at": "2026-08-06T10:00:00+05:30",
  "sequence": 42,
  "metrics": {
    "door_open": true,
    "battery_voltage": 4.8
  }
}
```

`observed_at` must contain a timezone and is normalized to UTC. The backend records a separate UTC `ingested_at`. Identifiers and metric names use a bounded safe character set, event types are allow-listed, sequences cannot be negative, metrics are bounded, and floating-point measurements must be finite. Unknown fields are rejected rather than silently discarded, and telemetry events require at least one metric.

Step 5 remains responsible for device registration, transport, authentication, heartbeat behaviour, and storing accepted live messages. Step 4 remains responsible for mapping both batch and live inputs into the canonical event model.
