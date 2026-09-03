# Deterministic Analysis Contract

Step 6 consumes version `1.0` canonical events from Step 4 and returns versioned, reproducible investigation artifacts. Python is the computational authority. APIs, real-time transport, storage of derived artifacts, email, reports, and AI narration remain separate later phases and must not recalculate these values.

## Pipeline

The `AnalysisService` executes this fixed order:

1. Verify that every event belongs to the requested case and that event IDs are unique.
2. Apply a validated `EventFilter` and stable sort with event ID as the final tie-breaker.
3. Execute versioned detection rules and behavioural baselines.
4. Create temporal correlation edges with explicit entity reasons.
5. Calculate bounded factorized risk scores.
6. Create pending alerts only when the rule's triggering event is live.
7. Group deterministic correlation components containing findings into incidents.
8. Build stable timelines, device/entity graph data, and chart-ready aggregates.

Identical events, configuration, and filter values produce exactly equal identifiers, ordering, scores, correlations, incidents, timelines, graphs, and chart points. `AnalysisResult` includes the complete validated configuration used for the run.

## Filters and ordering

Filters may select canonical event types, batch/live origins, device identities, source labels, and inclusive observed-time bounds. Filter lists are de-duplicated and sorted before analysis. Supported stable sort fields are `observed_at`, `ingested_at`, `event_type`, and `event_id`, in ascending or descending order.

Observed-time filtering never substitutes ingestion time. Events without `observed_at` do not satisfy an observed-time bound. In an observed-time sort or timeline, timed events are ordered first and untimed events remain explicitly marked `timestamp_basis: unavailable`.

## Rule set `1.1`

| Rule | Deterministic condition | Default output |
| --- | --- | --- |
| `LABEL-001` | TON_IoT network or telemetry label is `1`; CICIoT2023 label is outside the versioned benign set; other source labels use the versioned malicious allow-list. Matches are grouped by evidence, primary entity, and persisted attack class. | Medium, high, or critical severity based on the normalized attack class; 95 confidence |
| `RATE-001` | Numeric `attributes.requests` is at least three times positive numeric `attributes.baseline` | High severity, 90 confidence |
| `AUTH-001` | Ten authentication failures for the same known target entity and known actor occur within 60 observed seconds | Critical severity, 98 confidence |
| `BASELINE-001` | A telemetry metric exceeds its previous-sample mean plus the greater of three population standard deviations or the minimum delta | High severity, 80 confidence |

Every finding exposes its rule/version, condition trace, supporting event IDs, triggering event IDs, evidence IDs, confidence, and whether the actual trigger was live. Authentication failures with a missing actor or missing target identity are not grouped under a shared placeholder and therefore cannot trigger `AUTH-001`. A source label is evidence supplied by a selected dataset or adapter; matching it is a transparent rule result, not an independent claim about intent. Rule set `1.0` artifacts remain readable; `1.1` changes `LABEL-001` grouping and therefore produces a new deterministic analysis ID.

The default behavioural baseline requires three prior samples and retains at most twenty. It is calculated independently per primary entity and scalar telemetry metric. Boolean values and the transport `sequence` field are not treated as measurements. Each evaluated baseline stores its sample IDs, window, mean, population standard deviation, threshold, and evaluated event ID.

## Risk score `1.0`

Risk is an integer from 0 to 100. The five stored factor scores and default weights are:

| Factor | Weight | Source |
| --- | ---: | --- |
| Severity | 30% | Versioned rule severity mapping |
| Confidence | 25% | Versioned rule confidence |
| Repetition | 20% | Observed count relative to a rule-specific configured reference |
| Device criticality | 15% | Case configuration, default 50 |
| Corroboration | 10% | Declared correlation edges or multiple evidence objects |

The versioned default repetition references are `4` for `LABEL-001`, `4` for `RATE-001`, the configured authentication failure threshold (default `10`) for `AUTH-001`, and `3` for `BASELINE-001`. These values are explicit `AnalysisConfig` fields rather than hidden scoring constants. For example, one default `LABEL-001` occurrence produces a repetition factor of `25` and an overall default risk score of `59`.

Weighted integer points use deterministic largest-remainder allocation and always sum to the published score. Bands are low `0-24`, medium `25-49`, high `50-74`, and critical `75-100`. Risk expresses deterministic triage priority; it does not prove compromise, attribution, intent, or causation.

## Correlation and incidents

Two events receive a correlation edge only when both have observed timestamps, fall within the configured default 120-second window, and share at least one declared key:

- device identity;
- actor identity;
- target identity; or
- a normalized network address.

Each edge records the event pair, exact difference in seconds, window, version, and sorted reasons. Sharing a collector alone is deliberately insufficient. Correlation indicates a reproducible relationship for investigation, not causation.

NetworkX groups complete connected components. Only components containing at least one finding become incidents. An incident retains all component event, finding, and alert IDs, observed start/end when available, maximum risk, case ID, and version. Correlation-edge references are ordered deterministically by temporal proximity and capped at 4,096 per incident so dense datasets cannot make the analysis payload invalid. Each incident also reports the complete correlation-edge count and whether its retained reference list was truncated. This bounded-reference behavior is identified by the versioned `incident_reference_policy_version` analysis configuration field so upgraded reanalysis cannot collide with snapshots created before the policy existed.

## Timelines, graphs, aggregates, and alerts

Timelines contain canonical events plus derived findings and pending alerts. Ties are ordered event, finding, then alert. Observed and ingestion timestamps stay separate, and unavailable observed time remains null.

NetworkX produces deterministic entity nodes and aggregated relationship edges with contributing event IDs and counts. Node risk is the maximum risk of a finding supported by that node's events. Pandas produces sorted counts for event type, origin, source label, finding severity, risk band, and observed activity by UTC minute. These structures are backend-calculated inputs for Step 8 APIs and Step 9 visualizations.

Alerts are created only for findings whose declared triggering event is live. Historical batch findings remain findings but do not become live alerts. Step 6 marks alerts `pending`; Step 7 may deliver them and Step 11 may persist or notify after their own controls, without altering the forensic result.

## Current boundary

Step 6 remains the deterministic authority for filtering, detection, risk,
correlation, incidents, timelines, graphs, and aggregates. Step 8 now persists
complete analysis runs and queryable derived artifacts, exposes case-scoped and
historical investigation endpoints, and supplies generated response contracts
to the React client. Reanalysis over unchanged canonical events is idempotent.

Streaming, notification delivery, report generation, and AI narration remain
separate consumers of persisted results. They may present or deliver Step 6
outputs, but they must not recalculate or alter the forensic result.
