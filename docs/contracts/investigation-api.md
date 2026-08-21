# Investigation API Contract

Step 8 exposes persisted Step 3 validation reports, Step 4 canonical events, and
Step 6 deterministic analysis results under `/api/v1/cases`. The API does not
recompute forensic values in the frontend and does not accept client-supplied
findings, risk scores, alerts, incidents, graphs, timelines, or chart values.

## Resources

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/cases` | Create an investigation case |
| `GET` | `/cases` | List cases |
| `GET` | `/cases/{case_id}` | Read one case |
| `POST` | `/cases/{case_id}/evidence` | Validate raw CSV/JSON evidence, normalize accepted rows, and persist canonical events |
| `GET` | `/cases/{case_id}/evidence` | List validation reports and issues |
| `GET` | `/cases/{case_id}/evidence/{evidence_id}` | Read one validation report |
| `GET` | `/cases/{case_id}/events` | List canonical events with type, origin, evidence, and pagination filters |
| `GET` | `/cases/{case_id}/events/{event_id}` | Read one event with full provenance |
| `POST` | `/cases/{case_id}/analysis/reanalyze` | Run the deterministic engine over stored canonical events using an optional `EventFilter` |
| `GET` | `/cases/{case_id}/analysis` | Refresh the latest persisted analysis snapshot |
| `GET` | `/cases/{case_id}/analysis/runs` | List historical analysis snapshots |
| `GET` | `/cases/{case_id}/analysis/runs/{analysis_id}` | Read a specific snapshot |
| `GET` | `/cases/{case_id}/findings` | Read findings and five-factor risk breakdowns |
| `GET` | `/cases/{case_id}/alerts` | Read deterministic live-trigger alerts |
| `GET` | `/cases/{case_id}/incidents` | Read correlated incidents |
| `GET` | `/cases/{case_id}/timeline` | Read the stable investigation timeline |
| `GET` | `/cases/{case_id}/graph` | Read entity graph nodes and edges |
| `GET` | `/cases/{case_id}/charts` | Read chart-ready deterministic aggregates |

`analysis_id` may be supplied to the findings, alerts, incidents, timeline,
graph, and charts endpoints to review a historical snapshot. Without it, the
latest snapshot is returned.

Findings, alerts, and incidents also provide `/{resource_id}` detail endpoints.
These detail responses retain their supporting canonical event and evidence
identifiers so the UI can navigate back to source provenance.

## Evidence request

The evidence request body is the original file bytes. `filename` and
`source_type` are required query parameters, and `Content-Type` is preserved as
evidence metadata. A successful validation and normalization returns `201`. A
domain-level evidence rejection returns `200` with its structured validation
report and no canonical events, allowing the frontend to display exact Step 3
issues. Invalid API parameters and schemas return `422`; unknown case-scoped
resources return `404`.

Only Step 3-accepted rows cross into Step 4. The response separates Step 3
validation issues from any Step 4 normalization failures. Persisted canonical
events retain evidence IDs, source hashes, row references, adapter versions, and
normalization warnings.

## Persistence and determinism

Canonical events and complete `AnalysisResult` snapshots are stored as
versioned JSON alongside indexed case, evidence, time, type, and origin fields.
Event and analysis identifiers are content-derived by the existing Step 4 and
Step 6 services. Reusing one of those identifiers for different content is
rejected rather than overwriting forensic history. Repeating an identical
analysis is idempotent; changing the filter or event set creates a distinct
snapshot.

Batch findings never become live alerts. Alert creation continues to require a
qualifying finding triggered by canonical events whose provenance origin is
`live`.
