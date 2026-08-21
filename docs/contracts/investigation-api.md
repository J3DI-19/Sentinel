# Investigation API Contract

Step 8 exposes persisted Step 3 validation reports, Step 4 canonical events,
and Step 6 deterministic analysis results below `/api/v1`. The React client is
generated from the checked-in OpenAPI schema and displays backend-calculated
values; it does not calculate or submit forensic findings, scores, incidents,
graphs, timelines, or chart values.

## Resources

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/cases` | Create an investigation case |
| `GET` | `/cases` | List cases with bounded pagination |
| `GET` | `/cases/{case_id}` | Read one case |
| `GET` | `/cases/{case_id}/summary` | Read the latest case metrics |
| `POST` | `/cases/{case_id}/imports` | Upload multipart evidence and queue validation |
| `GET` | `/imports/{import_id}` | Poll validation, commit, or failure state |
| `POST` | `/imports/{import_id}/commit` | Confirm normalization and analysis, including explicit partial acceptance |
| `POST` | `/imports/{import_id}/cancel` | Cancel an unfinished import |
| `GET` | `/cases/{case_id}/evidence` | List evidence and validation reports |
| `GET` | `/cases/{case_id}/evidence/{evidence_id}` | Read case-scoped evidence and validation issues |
| `GET` | `/cases/{case_id}/events` | Filter and paginate canonical events |
| `GET` | `/cases/{case_id}/events/{event_id}` | Read a case-scoped event with raw record and provenance |
| `POST` | `/cases/{case_id}/analyses` | Re-run deterministic analysis over stored events |
| `GET` | `/cases/{case_id}/analyses` | List historical analysis snapshots |
| `GET` | `/cases/{case_id}/analyses/latest` | Read the latest complete result |
| `GET` | `/cases/{case_id}/analyses/{analysis_id}` | Read a specific historical result |
| `GET` | `/cases/{case_id}/findings` | Read findings and factorized risk scores |
| `GET` | `/cases/{case_id}/alerts` | Read deterministic live-trigger alerts |
| `GET` | `/cases/{case_id}/incidents` | Read correlated incidents |
| `GET` | `/cases/{case_id}/timeline` | Read the stable investigation timeline |
| `GET` | `/cases/{case_id}/graph` | Read entity graph nodes and edges |
| `GET` | `/cases/{case_id}/aggregates` | Read chart-ready deterministic aggregates |
| `GET` | `/cases/{case_id}/charts` | Compatibility alias for chart aggregates |
| `GET` | `/dashboard/summary` | Read global case and event totals |

Global `/evidence/{evidence_id}`, `/events/{event_id}`, and
`/analyses/{analysis_id}` detail routes are retained for generated-client and
cross-case navigation. Case-scoped routes additionally verify ownership.

`analysis_id` can be supplied to findings, alerts, incidents, timeline, graph,
aggregates, and charts endpoints. Without it, the latest analysis is returned.

## Import workflow

Evidence is uploaded as multipart form data with a required `file` and
`source_type`. Optional form fields describe timezone, timestamp selection,
duplicate handling, and an investigator label. Validation is asynchronous and
returns `202`; clients poll the import resource until it reaches
`awaiting_commit`, `rejected`, `failed`, or another terminal state.

Rows accepted by Step 3 carry an authenticated validation seal. On commit, the
backend binds those rows to the persisted evidence identity, verifies the seal,
normalizes them through Step 4, persists canonical events, and runs Step 6.
When validation rejects individual rows, `allow_partial: true` is required to
confirm that only accepted rows should be committed. Exact duplicate evidence
hashes do not create duplicate canonical events.

## Persistence and determinism

Canonical events retain evidence IDs, source hashes, row references, adapter
versions, raw record hashes, and normalization warnings. Complete analysis
results and independently queryable artifacts are persisted as versioned JSON.
Event and analysis identifiers are content-derived. Repeating an unchanged
analysis is idempotent; attempting to reuse an identifier for different content
is rejected instead of overwriting forensic history.

Batch findings never become live alerts. Alerts require a qualifying finding
triggered by canonical events whose provenance origin is `live`.

Errors use a stable body containing `code`, `message`, `retryable`,
`request_id`, and optional `details`. Request IDs are also returned in the
`X-Request-ID` header.
