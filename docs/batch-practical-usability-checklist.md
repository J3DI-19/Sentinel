# Batch Practical Usability Checklist

This checklist defines the work required before Traceveil's batch-only workflow
can be considered practically usable by someone who is not familiar with the
codebase.

## Purpose: university second-review showcase

This document is the readiness gate for Traceveil's **second review showcase at
the university**. The showcase target is a coherent, repeatable batch
investigation demonstration: a reviewer should be able to start the software,
create a case, import evidence, validate and persist it, run deterministic
analysis, inspect traceable results, and reopen those results without relying on
unfinished roadmap features.

Passing this checklist means the batch showcase is practically usable and ready
to demonstrate. It does not mean the complete Traceveil roadmap or a
production-ready deployment is finished.

## Roadmap steps accounted for

This checklist verifies the usable batch path formed by the following roadmap
work:

| Roadmap step | Showcase coverage |
| --- | --- |
| **Step 1 — Initialization** | React/Vite frontend, FastAPI backend, SQLite persistence, frontend/backend connection, installation, startup, and health behaviour required by the batch workflow. Ollama is not required. |
| **Step 2 — Frontend and Investigation Interface** | Application shell, navigation, case pages, evidence import, connected investigation dashboard, result tables, metrics, and batch-focused error and empty states. Live, chat, email, and report areas are outside this showcase. |
| **Step 3 — Input Check and Evidence Validation** | Supported batch files, size and structure checks, required fields, invalid-value handling, hashes, source metadata, validation errors, and the selected batch dataset profiles. Live telemetry validation is excluded. |
| **Step 4 — Canonical Event Model and Normalization** | Canonical event creation for uploaded evidence, timestamp and entity normalization, source-row references, provenance, and the supported batch adapters. Live normalization is excluded from showcase acceptance. |
| **Step 6 — Filtering, Detection, Risk and Correlation** | Deterministic batch filtering, sorting, rules, baselines, bounded risk scoring, correlation, incidents, timelines, graph data, and chart-ready aggregates. Live triggers are excluded. |
| **Step 8 — Dashboard Results and Investigation APIs** | Persisted case/evidence/event APIs, batch analytical results in the connected dashboard, manual refresh and reanalysis, provenance and evidence references, and historical batch analysis review. Live-incident completion remains deferred. |

The checklist is therefore an integration and usability gate across Steps 1, 2,
3, 4, 6, and the batch-only portion of Step 8. It does not replace the detailed
technical acceptance criteria within those roadmap steps.

## Scope

This usability gate includes case creation, evidence import and validation,
canonical event creation, deterministic analysis, persisted investigation
results, reanalysis, and historical batch review.

It explicitly excludes:

- Live IoT ingestion and physical devices from Step 5.
- Real-time event delivery from Step 7.
- Alert notification or delivery workflows.
- Email and broader automation.
- AI assistance and narration.
- Later visualization-engine work.

The deterministic engine may still produce finding, risk, incident, and other
analytical records. The exclusions above apply to live and notification
workflows, not to the batch engine's persisted analytical output.

## Phase 1: Implementation

Complete the required product behaviour and user-facing workflow before fixing
interaction defects or running acceptance checks.

### 1. Batch configuration and service-state messaging

- [x] Provide working `.env.example` defaults for batch-only use.
- [x] Show a clear message when the backend or database is unavailable.

### 2. Case workflow

- [x] Allow users to create a case successfully.
- [x] Automatically select the newly created case when entering the import page.
- [x] Prevent importing without a valid persisted case.
- [x] Provide clear empty states when no cases exist.

### 3. Evidence-import workflow

- [x] Clearly document supported columns and source profiles.
- [x] Provide at least one small working example evidence file.
- [x] Show understandable validation errors with source-row references.
- [x] Make partial-import approval clear and deliberate.
- [x] Prevent duplicate submission while an import is running.
- [x] Add an **Open case results** action after a successful import.
- [x] Either implement **View import history** or remove the disabled control
  until that functionality exists.

### 4. Analysis and result presentation

- [x] Clearly distinguish "analysis completed with no findings" from an analysis
  failure.
- [x] Show evidence, canonical events, findings, incidents, timelines, risk
  factors, provenance, graph data, and aggregates from persisted backend data.
- [x] Handle cases with no evidence or no analysis without crashing.
- [x] Display meaningful loading, empty, partial-result, and error states.
- [x] Ensure displayed identifiers and evidence references can be followed back
  to their source records.

### 5. Historical batch analysis

- [x] Add a visible Analysis History entry point.
- [x] List persisted batch-analysis snapshots.
- [x] Let users select a historical snapshot.
- [x] Load the selected snapshot's findings, incidents, timeline, graph, charts,
  and aggregates using its `analysis_id`.
- [x] Clearly identify whether the user is viewing the latest or a historical
  analysis.
- [x] Preserve or intentionally reset the selected snapshot during navigation.

## Phase 2: Functional fixes and recovery

Resolve known interaction defects and make the implemented workflow resilient
before beginning final verification.

### 6. Refresh and error recovery

- [x] Add a working refresh control to the connected case workspace.
- [x] Make **Retry** execute the failed request directly.
- [x] Prevent stale responses from overwriting newer results.
- [x] Preserve the current tab, filter, page, and selected snapshot during
  refresh.

### 7. Reanalysis

- [x] Fix reanalysis when the user is already on the Findings page.
- [x] Prevent the interface from remaining stuck in a loading state.
- [x] Disable or safely deduplicate the control while reanalysis is running.
- [x] Refresh the case summary and analytical result tabs after completion.
- [x] Clearly report whether reanalysis created a new snapshot or reused an
  identical persisted snapshot.

## Phase 3: Verification and acceptance

Run these checks only after the implementation and functional-fix phases are
complete.

### 8. Integration verification

- [ ] Confirm a clean machine can install the backend and frontend using only
  the README instructions.
- [ ] Verify database tables are created automatically on first run.
- [ ] Confirm the application works without Ollama, SMTP, hardware, or
  live-telemetry configuration.
- [ ] Confirm cases and their data remain available after restarting the
  backend.
- [ ] Confirm CSV and JSON imports work through the browser.
- [ ] Confirm cancellation and retry behave correctly.
- [ ] Verify failed imports do not accidentally create partial evidence, events,
  or analysis snapshots.
- [ ] Confirm committing an import automatically produces an analysis result.
- [ ] Confirm temporary backend failures can be recovered from without
  restarting the frontend.

### 9. Automated verification

- [ ] Add frontend tests for Refresh, Retry, reanalysis, history selection, and
  post-import navigation.
- [ ] Run the complete backend test suite.
- [ ] Run the complete frontend test suite.
- [ ] Run TypeScript checking.
- [ ] Run the production frontend build.
- [ ] Confirm generated OpenAPI types are current.
- [ ] Confirm no production route silently falls back to mock data.
- [ ] Confirm an imported case remains usable after restarting both
  applications.

### 10. Final usability smoke test

A person unfamiliar with the codebase must be able to complete the following
workflow without developer assistance:

- [ ] Follow the README and start the backend and frontend.
- [ ] Create a case.
- [ ] Upload the provided example evidence.
- [ ] Understand and approve its validation result.
- [ ] Open the imported case.
- [ ] Review its evidence and canonical events.
- [ ] Review the latest deterministic analysis.
- [ ] Follow an analytical result back to supporting evidence.
- [ ] Reanalyze the case successfully.
- [ ] Refresh the results.
- [ ] Select and review an older analysis snapshot.
- [ ] Restart the application and find the case and results still intact.
- [ ] Recover from a temporarily unavailable backend using **Retry**.

## Completion rule

The batch-only application can be described as practically usable when every
non-excluded checklist item above passes on a clean setup. Completion of this
document does not imply support for live ingestion, physical hardware,
real-time delivery, notifications, email, AI, or later roadmap features.
