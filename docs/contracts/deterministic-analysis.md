# Deterministic Analysis Contract

Step 6 consumes version `1.0` canonical events from Step 4 and returns versioned, reproducible investigation artifacts. Python is the computational authority. APIs, real-time transport, storage of derived artifacts, email, reports, and AI narration remain separate later phases and must not recalculate these values.

## Pipeline

The `AnalysisService` executes this fixed order:

1. Verify that every event belongs to the requested case and that event IDs are unique.
2. Apply a validated `EventFilter` and stable sort with event ID as the final tie-breaker.
3. Execute versioned detection rules and behavioural baselines.
4. Create temporal correlation edges with explicit entity reasons.
5. Apply the versioned classification taxonomy and calculate bounded factorized risk scores with explicit evidence-quality penalties.
6. Create pending alerts only when the rule's triggering event is live.
7. Group related findings into bounded, finding-centred incident sessions.
8. Build stable timelines, device/entity graph data, and chart-ready aggregates.

Identical events, configuration, and filter values produce exactly equal identifiers, ordering, scores, correlations, incidents, timelines, graphs, and chart points. `AnalysisResult` includes the complete validated configuration used for the run.

## Filters and ordering

Filters may select canonical event types, batch/live origins, device identities, source labels, and inclusive observed-time bounds. Filter lists are de-duplicated and sorted before analysis. Supported stable sort fields are `observed_at`, `ingested_at`, `event_type`, and `event_id`, in ascending or descending order.

Observed-time filtering never substitutes ingestion time. Events without `observed_at` do not satisfy an observed-time bound. In an observed-time sort or timeline, timed events are ordered first and untimed events remain explicitly marked `timestamp_basis: unavailable`.

## Rule set `1.4`

| Rule | Deterministic condition | Default output |
| --- | --- | --- |
| `LABEL-001` | TON_IoT network or telemetry label is `1`; CICIoT2023 label is outside the versioned benign set; other source labels use the versioned malicious allow-list. Matches are grouped by evidence, primary entity, persisted attack class, and a bounded temporal session. | Medium, high, or critical severity based on the normalized attack class; 95 confidence |
| `RATE-001` | Numeric `attributes.requests` is at least three times positive numeric `attributes.baseline` | High severity, 90 confidence |
| `AUTH-001` | Ten authentication failures for the same known target entity and known actor occur within 60 observed seconds | Critical severity, 98 confidence |
| `BASELINE-001` | A telemetry metric exceeds its previous-sample mean plus the greater of three population standard deviations or the minimum delta | High severity, 80 confidence |
| `TELEMETRY-ROC-001` | An absolute telemetry change exceeds the rolling median change by the configured multiplier | High severity, 82 confidence |
| `NET-FANOUT-001` | A source reaches the configured number of distinct destinations inside the network window | High severity, 85 confidence |
| `NET-PORTSCAN-001` | A source reaches the configured number of destination/port combinations inside the network window | High severity, 88 confidence |
| `NET-FAILURE-001` | Failed or incomplete network connections reach the configured threshold inside the network window | High severity, 90 confidence |

Every finding exposes its rule/version, condition trace, affected canonical device ID, supporting event IDs, triggering event IDs, evidence IDs, confidence, and whether the actual trigger was live. Authentication failures with a missing actor or missing target identity are not grouped under a shared placeholder and therefore cannot trigger `AUTH-001`. A source label is evidence supplied by a selected dataset or adapter; matching it is a transparent rule result, not an independent claim about intent. Rule set `1.0` through `1.4` artifacts remain readable; `1.2` adds label-independent telemetry and network behavior rules. Rule set `1.3` includes the classified metric and condition identity in deterministic finding IDs, preventing distinct HAI metrics supported by the same event pair from colliding during persistence. Rule set `1.4` bounds dataset-label findings by inactivity, trigger span, and record count so one source class cannot turn an entire file into one finding.

The default behavioural baseline requires three prior samples and retains at most twenty. It is calculated independently per primary entity and scalar telemetry metric. Boolean values and the transport `sequence` field are not treated as measurements. Each evaluated baseline stores its sample IDs, window, mean, population standard deviation, threshold, and evaluated event ID.

## Classification taxonomy `1.1`

Every new finding contains a structured classification with category, subcategory,
display name, normalized category/subcategory tags, source field/value, confidence, and provenance. Provenance is one of
`dataset_label`, `deterministic_rule`, `behavioral_anomaly`,
`investigator_assigned`, or `ai_suggestion`. TON_IoT names such as DDoS are
reported as **dataset-labelled**, because the name comes from the source `type`
column rather than an independent Traceveil inference. Exact, versioned aliases
replace substring classification. Unknown malicious values remain visible under
`unknown/malicious`, receive lower classification confidence, and incur an
explicit risk-quality penalty.

## Risk score `1.1`

Risk is an integer from 0 to 100. The five stored factor scores and default weights are:

| Factor | Weight | Source |
| --- | ---: | --- |
| Severity | 30% | Versioned rule severity mapping |
| Confidence | 25% | Versioned rule confidence |
| Repetition | 20% | Observed count relative to a rule-specific configured reference |
| Device criticality | 15% | Case configuration, default 50 |
| Corroboration | 10% | Declared correlation edges or multiple evidence objects |

The versioned default repetition references are `4` for `LABEL-001`, `4` for `RATE-001`, the configured authentication failure threshold (default `10`) for `AUTH-001`, and `3` for `BASELINE-001`. These values are explicit `AnalysisConfig` fields rather than hidden scoring constants. For example, one default `LABEL-001` occurrence produces a repetition factor of `25` and an overall default risk score of `59`.

Weighted integer points use deterministic largest-remainder allocation and sum to
the stored `base_score`. Version 1.1 then subtracts explicit, stored penalties for
unknown identity, missing observed time, and generic unverified attack classes.
The resulting score remains bounded at zero. Bands are low `0-24`, medium
`25-49`, high `50-74`, and critical `75-100`. Evidence confidence and
classification confidence are stored separately. Risk expresses deterministic
triage priority; it does not prove compromise, attribution, intent, or causation.

## Correlation and incidents

Two events receive a correlation edge only when both have observed timestamps, fall within the configured default 120-second window, and share at least one declared key:

- device identity;
- actor identity;
- target identity; or
- a normalized network address; or
- a shared normalized service name.

Each edge records the event pair, exact difference in seconds, window, version, and sorted reasons. Sharing a collector alone is deliberately insufficient. Correlation indicates a reproducible relationship for investigation, not causation.

Correlation version `1.1` first limits the graph to events that actually support a finding. This prevents otherwise-related background traffic from being swept into an incident. Related findings may still converge across telemetry and network evidence when timestamps overlap and they share a deliberately preserved device, network, or service identity.

Within each related component, incident grouping version `1.0` creates deterministic sessions using finding trigger time. A new session begins after 120 seconds of inactivity, when adding the next finding would put the first and last triggers more than 120 seconds apart, or when the event-reference limit would be exceeded. Supporting baseline context may begin before the first trigger, so the displayed incident start/end can be slightly wider than the trigger span. Untimed findings remain separate from timed sessions because a temporal relationship cannot be established.

An incident retains its supporting event, finding, and alert IDs, observed context start/end, maximum risk, peak severity, severity distribution, distinct evidence counts, explicit entity IDs, case ID, and grouping policy. Correlation-edge references are ordered deterministically by temporal proximity and capped at 4,096 per incident. Finding and alert references are capped at 1,024 each. Complete counts and explicit truncation flags preserve the true scope when a retained reference list is bounded. This behavior is versioned in the analysis configuration so upgraded reanalysis cannot collide with earlier snapshots.

## Timelines, graphs, aggregates, and alerts

Timelines contain canonical events plus derived findings and pending alerts. Ties are ordered event, finding, then alert. Observed and ingestion timestamps stay separate, and unavailable observed time remains null.

NetworkX produces deterministic entity nodes and aggregated relationship edges with contributing event IDs and counts. Node risk is the maximum risk of a finding supported by that node's events. Pandas produces sorted counts for event type, origin, source label, finding severity, risk band, and observed activity by UTC minute. These structures are backend-calculated inputs for Step 8 APIs and Step 9 visualizations.

Alerts are created only for findings whose declared triggering event is live. Historical batch findings remain findings but do not become live alerts. Step 6 marks alerts `pending`; Step 7 may deliver them and Step 11 may persist or notify after their own controls, without altering the forensic result.

The immutable alert artifact remains part of the analysis snapshot. A separate
mutable workflow record tracks `pending`, `acknowledged`, `resolved`, or
`suppressed`, including actor and update time, without rewriting forensic output.
The same workflow record separately tracks notification delivery as
`not_requested`, `delivered`, or `delivery_failed`, with a bounded error message.

Each observed UTC minute also receives an activity-window explanation containing
the event count, median minute baseline, ratio, volume-anomaly flag, leading event
types/devices, source classifications, and overlapping finding/incident IDs.
Explanations explicitly distinguish source-supplied classes, deterministic rule
context, and `undetermined`; record volume alone never creates a security finding.

## Current boundary

Step 6 remains the deterministic authority for filtering, detection, risk,
correlation, incidents, timelines, graphs, and aggregates. Step 8 now persists
complete analysis runs and queryable derived artifacts, exposes case-scoped and
historical investigation endpoints, and supplies generated response contracts
to the React client. Reanalysis over unchanged canonical events is idempotent.

Streaming, notification delivery, report generation, and AI narration remain
separate consumers of persisted results. They may present or deliver Step 6
outputs, but they must not recalculate or alter the forensic result.
