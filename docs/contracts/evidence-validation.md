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

`validate_with_records` is the Step 3-to-Step 4 boundary. In addition to the report, it returns a `ValidatedBatchRecord` for each accepted row and never returns rejected rows. Each handoff contains the evidence ID, source type, dataset profile, validator version, original row number, parsed record, a deterministic SHA-256 record hash, and an HMAC authorization seal over those claims plus the original evidence hash. Step 4 verifies the metadata, recomputes the record hash, and verifies the seal with the same process-local authority before normalization. A caller that fabricates a row and its public SHA-256 hash cannot authorize it as Step 3 output.

## Versioned profiles

| Profile | Minimal required columns |
| --- | --- |
| `casas_milan@1.0` | `timestamp`, `sensor_id`, `sensor_message`; optional `activity` annotation |
| `ton_iot_fridge_telemetry@1.0` | `date`, `time`, `fridge_temperature`, `temp_condition`, `label`, `type` |
| `simulated@1.0` | `timestamp`, `device_id`, `event_type` |
| `ton_iot_network@1.0` | `ts`, `src_ip`, `dst_ip`, `label` |
| `ciciot2023_network@1.0` | `flow_duration`, `Protocol Type`, `label` |
| `generic@1.0` | No dataset-specific columns; structural checks still apply |

A small redistributable [`simulated@1.0` example](../../frontend/public/examples/simulated-evidence.csv) is provided for the connected import workflow. It contains synthetic records only. Select **Simulation** in the import page before uploading it. The table above remains the authoritative list of supported profile columns.

The two primary profiles are pinned to a CSV projection of the [CASAS Milan public smart-home dataset](https://casas.wsu.edu/datasets/index) catalog snapshot updated 2018-09-07 and the [2020 TON_IoT telemetry release](https://research.unsw.edu.au/projects/toniot-datasets)'s `Train_Test_IoT_Fridge.csv` subset. CASAS CSV records preserve the observed timestamp, sensor identity, message, and optional activity annotation. The fridge profile validates its release-specific date/time format, finite temperature, device state, binary label, and attack type.

CASAS smart-home telemetry and TON_IoT device telemetry are the primary public evaluation sources, supplemented by controlled simulation. The TON_IoT network and CICIoT2023 profiles remain secondary compatibility paths. The TON_IoT network profile intentionally names a separate network subset because TON_IoT contains heterogeneous sources. Additional CASAS testbeds or TON_IoT devices must receive separate versioned profiles instead of weakening these contracts. Small synthetic contract fixtures preserve the expected layouts without redistributing dataset records.

## Test-process completion guard

The test configuration reports leaked non-daemon threads at session shutdown. `backend/scripts/run_pytest_cleanly.py` also runs pytest as a child process with a configurable deadline, terminates the complete child process tree on expiry, and returns status `124`. CI invokes this wrapper and therefore requires both passing tests and a clean zero-code pytest process exit.

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

`observed_at` must contain a timezone and is normalized to UTC. `ingested_at` is not part of the caller-controlled input: the backend `LiveTelemetryAcceptanceService` assigns it from its own clock and normalizes it to UTC. Attempts to supply `ingested_at` directly are rejected. Identifiers and metric names use a bounded safe character set, event types are allow-listed, sequences cannot be negative, metrics are bounded, and floating-point measurements must be finite. Unknown fields are rejected rather than silently discarded, and telemetry events require at least one metric.

Step 5 remains responsible for device registration, transport, authentication, heartbeat behaviour, and storing accepted live messages. Step 4 remains responsible for mapping both batch and live inputs into the canonical event model.
