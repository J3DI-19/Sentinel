# Blind HAI and IoT-23 evaluation

Traceveil provides two label-free evidence profiles:

- `hai_ics_blind@1.0` for industrial telemetry;
- `iot23_zeek_blind@1.0` for Zeek connection records.

Both profiles reject known answer columns (`label`, `attack`, `attack_type`, `category`, and dataset-specific label variants). Classification is therefore based on versioned behavioral or deterministic rules, never on a hidden dataset answer.

## Device identity and converged cases

Every blind record requires `device_id`. Use the same value only when two evidence sources describe the same physical or logical device. For example, HAI telemetry and IoT-23-style network records using `edge-device-01` can be imported into one case and correlated through that canonical identity when their observed timestamps overlap. Different devices must receive different IDs even if they came from the same archive.

Network records additionally preserve source and destination IP entities. Traceveil can therefore correlate records through a shared device, actor, target, network address, or service inside the configured time window. A filename or dataset name never creates a correlation.

The HAI and IoT-23 examples under `datasets/sample` are label-free projections of real publisher data. Their devices and original timestamps remain distinct. They may be imported into one case for a unified investigation, but Traceveil will only create cross-source connections when evidence genuinely shares an entity or falls within a configured correlation rule. It will not invent a shared device. The frontend keeps web-download copies under `frontend/public/examples`.

## Preparing official downloads

The local full releases live under `datasets/full/originals/` and are ignored by Git. Create additional label-free CSV projections with:

```powershell
python backend/scripts/prepare_blind_dataset.py hai <hai.csv> <hai-blind.csv> --device-id hai-testbed-01 --device-name "HAI industrial testbed" --device-type industrial_control_system --timestamp-column timestamp
python backend/scripts/prepare_blind_dataset.py iot23 <conn.log.labeled> <iot23-blind.csv> --device-id somfy-01 --device-name "Somfy smart door lock" --device-type smart_door_lock
```

Keep the original label files outside Traceveil as a ground-truth answer key. Reveal them only after the analysis snapshot has been persisted.

## Current blind rules

- `BASELINE-001`: telemetry exceeds its rolling behavioral baseline.
- `TELEMETRY-ROC-001`: telemetry changes faster than its prior change distribution.
- `NET-FANOUT-001`: a source reaches an unusual number of destinations.
- `NET-PORTSCAN-001`: a source reaches an unusual number of destination/port combinations.
- `NET-FAILURE-001`: a source produces a burst of failed or incomplete connections.

Each finding preserves the canonical device ID, triggering event IDs, evidence IDs, condition trace, classification confidence, evidence confidence, risk factors, and penalties.
