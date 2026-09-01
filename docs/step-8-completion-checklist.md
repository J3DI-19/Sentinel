# Step 8 Completion Checklist

This checklist records the remaining work found during the Step 8 audit. The
backend investigation APIs are implemented and the existing automated checks
pass, but Step 8 should not be considered fully complete until the dashboard
workflows below are finished and verified.

## 1. Historical analysis review

- [ ] Add a visible **Analysis history** tab or equivalent entry point in the
  case workspace.
- [ ] List persisted analysis snapshots with their analysis ID, creation time,
  status, input fingerprint, and other useful identifying information.
- [ ] Allow the investigator to select a historical analysis snapshot.
- [ ] Pass the selected `analysis_id` when requesting findings, alerts,
  incidents, timeline, graph, aggregates, and chart data.
- [ ] Clearly distinguish the latest analysis from a historical snapshot in the
  interface.
- [ ] Allow persisted incidents originating from live capture to be reviewed in
  their historical analysis context.
- [ ] Provide appropriate empty, loading, invalid-snapshot, and API-error states.
- [ ] Add frontend tests covering snapshot listing, selection, navigation, and
  historical result retrieval.

### Acceptance criteria

- An investigator can reach analysis history without manually editing the URL.
- Selecting an older snapshot displays results from that snapshot rather than
  silently displaying the latest analysis.
- Refreshing or navigating between result tabs preserves the selected snapshot,
  or clearly returns the user to the latest analysis.

## 2. Refresh controls

- [ ] Add an explicit refresh control to the connected case workspace.
- [ ] Add an explicit refresh control to the connected overview, if that page is
  expected to show changing persisted activity without a browser reload.
- [ ] Make **Retry** execute the failed request directly instead of navigating to
  the same route.
- [ ] Prevent overlapping requests or stale responses when refresh is clicked
  repeatedly.
- [ ] Preserve the current filter, page, section, and selected analysis snapshot
  while refreshing.
- [ ] Add frontend tests for successful refresh, failed refresh, retry, and rapid
  repeated refreshes.

### Acceptance criteria

- Refresh visibly reloads the current dataset without requiring a route change
  or full browser reload.
- Retry recovers after a transient API failure on every connected case section.
- Loading and error indicators always settle after the request completes.

## 3. Reanalysis control

- [ ] Fix reanalysis when the user is already on the Findings section. The
  current same-route navigation does not trigger a new fetch and can leave the
  page in a permanent loading state.
- [ ] Refetch the relevant case summary and analytical results after reanalysis
  completes.
- [ ] Display a clear running, success, and failure state for reanalysis.
- [ ] Disable or safely deduplicate the control while a reanalysis request is in
  progress.
- [ ] Decide whether an idempotent reanalysis should select the existing
  snapshot or create/select a new snapshot, and communicate that result in the
  interface.
- [ ] Add frontend tests for reanalysis from Findings and from every other case
  section.

### Acceptance criteria

- Reanalyze works from every case-workspace section, including Findings.
- The resulting analysis is selected or displayed after the operation.
- The page never remains stuck in a loading state.

## 4. Generated API types

- [ ] Replace `unknown`, `Record<string, unknown>`, and locally duplicated API
  response shapes in the connected investigation workspace with generated
  OpenAPI types where schemas are available.
- [ ] Add or refine backend response schemas where generated types are too vague
  to model investigation results safely.
- [ ] Type findings, alerts, incidents, timeline entries, graph data, aggregates,
  charts, analysis history, evidence, events, and case summaries.
- [ ] Ensure regeneration of `frontend/src/api/generated.ts` is reproducible and
  checked by CI.
- [ ] Confirm the UI still preserves backend IDs, UTC timestamps, null values,
  provenance, rule traces, risk factors, and supporting evidence identifiers.

### Acceptance criteria

- Core connected investigation views consume generated API response types.
- TypeScript reports incompatible backend/frontend contract changes during CI.
- The Step 8 completion statement about generated OpenAPI types is factually
  accurate.

## 5. Verification and roadmap closure

- [ ] Add connected-page frontend coverage for analysis history, refresh, Retry,
  and reanalysis workflows.
- [ ] Run the complete backend test suite.
- [ ] Run the complete frontend test suite.
- [ ] Run TypeScript checking and the production frontend build.
- [ ] Confirm the generated OpenAPI document and frontend types are current.
- [ ] Manually smoke-test a case containing imported evidence, canonical events,
  multiple analysis snapshots, alerts, incidents, timeline entries, graph data,
  charts, risk factors, evidence IDs, and provenance references.
- [ ] Verify historical live incidents remain reviewable after newer analyses
  have been created.
- [ ] Update `docs/roadmap.md` only after every acceptance criterion above passes.
- [ ] Remove or revise the statement that Step 8 is complete if any item remains
  intentionally out of scope.

## Already verified during the audit

- [x] Production routes use connected pages backed by persisted APIs.
- [x] Case, evidence, event, alert, incident, timeline, graph, chart, aggregate,
  dashboard, and analysis-history endpoints exist.
- [x] Investigation APIs expose risk factors, supporting evidence identifiers,
  and event provenance/source references.
- [x] Backend tests cover analysis history retrieval and idempotent reanalysis.
- [x] The existing backend tests, frontend tests, TypeScript check, production
  build, and GitHub checks passed at the audited revision.
