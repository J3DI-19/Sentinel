# Step 8 Verification

Step 8 is accepted for the persisted batch-investigation scope. Physical IoT
ingestion and real-time browser delivery are separate Step 5 and Step 7 work.

## Covered workflows

- The case workspace exposes visible analysis history with IDs, UTC creation
  times, status, input fingerprints, result counts, and latest/historical labels.
- Selecting a snapshot stores its `analysis` ID in the URL and sends it to the
  findings, alerts, incidents, timeline, graph, aggregates, and chart endpoints.
- Manual Refresh and Retry rerun the active request without losing its filter,
  page, section, or selected snapshot. Abort and sequence guards prevent stale
  responses from replacing newer results.
- Reanalysis is disabled while running, reports success or failure, reuses an
  existing snapshot for unchanged inputs, and selects the resulting snapshot.
- Connected investigation views use OpenAPI-generated response types.

## Reproducible verification

Run these commands from the repository root:

```powershell
cd backend
python scripts/run_pytest_cleanly.py --timeout 180 -- -q
python export_openapi.py ../frontend/src/api/openapi.json --check

cd ../frontend
npm run api:types
git diff --exit-code -- src/api/generated.ts
npm run lint
npm test
npm run build
```

The backend integration coverage imports evidence, creates multiple immutable
analysis snapshots, and verifies that an older snapshot's incidents remain
queryable after a newer snapshot exists. It also checks selected-snapshot
findings, alerts, incidents, timeline, graph, aggregates, charts, risk factors,
supporting evidence IDs, and provenance references. The connected-page tests
exercise the same history, navigation, refresh, Retry, and reanalysis workflows
at the UI/API boundary.

A separate controlled persisted live-shaped fixture creates an alert and then
reads that alert and its timeline through a selected historical analysis ID. It
is contract coverage only and is not evidence of physical or real-time operation.

## Manual UI smoke result

On 2026-09-01, the connected application was run against a temporary SQLite
case containing two committed evidence imports and two analysis snapshots. The
browser smoke covered the visible history entry point, historical selection and
URL persistence, findings and risk details, incidents, timeline, graph, charts,
manual refresh, evidence, event provenance, and idempotent reanalysis. The first
pass exposed stale prior-section data during graph navigation; the route-data
guard and its regression test were added, and the repeated smoke passed. The
temporary servers and database were removed after verification.

A second temporary case used the controlled live-shaped contract fixture to
persist an `AUTH-001` alert. The Alerts view rendered its backend ID, title,
severity, risk score, UTC trigger time, and explicit analysis-snapshot context.
This verifies only the persisted Step 8 contract and UI; Steps 5 and 7 remain
the acceptance owners for genuine collection and real-time delivery.

## Deferred acceptance

Controlled persisted live-shaped records may be rendered through the same API
contracts, but they do not demonstrate genuine live operation. Device transport,
registration, heartbeat, and end-to-end ingestion are Step 5. SSE/WebSocket
delivery, reconnect behaviour, and real-time dashboard updates are Step 7.
