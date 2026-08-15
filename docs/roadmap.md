# Traceveil Roadmap

## 1. Initialization
- [x] Set up React + Vite frontend
- [x] Set up FastAPI backend
- [x] Set up SQLite
- [x] Install required libraries
- [x] Connect frontend and backend
- [x] Add Ollama configuration and optional availability/model health checks
- [x] Install Ollama, pull the selected Qwen 9B Q4_K_M model, and verify it locally

**Current result:** Step 1 is complete. The Traceveil frontend connects to
FastAPI and reports API, SQLite, and Ollama health. Backend health tests pass (4
tests), and the frontend test suite passes (14 tests). Traceveil remains usable
when Ollama is offline.

## 2. Frontend and Investigation Interface
- [x] Build the initial Step 1 service-status shell
- [x] Build the global application layout and navigation
- [x] Build case pages
- [x] Build evidence upload/import page
- [x] Build main investigation dashboard
- [x] Add metric and severity cards
- [x] Add evidence tables
- [x] Add chart placeholders
- [x] Add incident timeline placeholder
- [x] Add device/entity graph placeholder
- [x] Add recommendations/findings panels
- [x] Add live monitoring status indicators
- [x] Add live event feed
- [x] Add live alert feed
- [x] Add device connection/status components
- [x] Add chat section
- [x] Add email/report sections
- [x] Use structured mock data before backend feature integration

**Current result:** Step 2 is complete. The frontend now provides the global
application shell, case workspaces, evidence import flow, investigation
dashboard, metrics, evidence tables, deterministic visualizations, timeline,
entity graph, findings, live-monitoring views, Investigation Assistant, and
report review experience. These interfaces currently use structured mock data;
backend evidence ingestion and analytical integration begin in Step 3.

## 3. Input Check and Evidence Validation
- [x] Accept supported evidence file types
- [x] Check file size and structure
- [x] Validate required columns
- [x] Detect missing or invalid values
- [x] Hash and store evidence metadata
- [x] Preserve source metadata
- [x] Return structured validation errors for later API/frontend integration
- [x] Define validated live telemetry input contracts
- [x] Validate incoming device identifiers and event types
- [x] Reject malformed live telemetry
- [x] Record live ingestion timestamps
- [x] Preserve source/device provenance for live evidence
- [x] Validate the pinned CASAS Milan native text subset
- [x] Validate the pinned TON_IoT fridge telemetry subset
- [x] Require pytest to terminate cleanly in CI

## 4. Canonical Event Model and Normalization
- [x] Create the common canonical event schema
- [x] Map simulated data
- [x] Map CASAS Milan smart-home sensor data
- [x] Map TON_IoT fridge device telemetry
- [x] Map TON_IoT data
- [x] Map CICIoT2023 data
- [x] Standardize timestamps
- [x] Standardize device and entity fields
- [x] Preserve source row references
- [x] Create a live telemetry adapter
- [x] Normalize live device events into the canonical event model
- [x] Preserve live source and ingestion metadata

**Convergence point:** Uploaded/batch evidence and accepted live telemetry both
become canonical events and enter the same deterministic investigation pipeline.

## 5. Live IoT Integration
- [ ] Select the Arduino-compatible microcontroller
- [ ] Select the IoT test device or endpoint
- [ ] Define the controlled laboratory topology
- [ ] Define the live telemetry message format
- [ ] Implement device-to-backend telemetry transport
- [ ] Support MQTT and/or HTTP based on the chosen implementation
- [ ] Build the backend live event collector
- [ ] Add device registration/identification
- [ ] Add connection and heartbeat status
- [ ] Store accepted live telemetry as evidence
- [ ] Forward normalized live events into the common analysis pipeline
- [ ] Prepare controlled suspicious-event scenarios for demonstration
- [ ] Verify end-to-end live ingestion

## 6. Filtering, Detection, Risk and Correlation
- [x] Add deterministic filters
- [x] Add stable sorting
- [x] Add detection rules
- [x] Add behavioural baselines
- [x] Add bounded risk scoring
- [x] Add event correlation
- [x] Build incident timelines
- [x] Generate graph data
- [x] Generate chart-ready aggregates
- [x] Support analysis of both batch and live events
- [x] Trigger alerts from qualifying live events

**Current result:** Step 6 is complete. The backend provides a versioned
deterministic analysis service over canonical batch and live events. It returns
rule traces, baseline samples, bounded five-factor risk scores, explicit
correlation reasons, incident components, stable timelines, NetworkX graph
data, Pandas chart aggregates, and pending alerts for actual live triggers.
Golden and adversarial tests verify reproducibility, phase boundaries, missing
observed time, stable filtering, and batch/live alert behaviour. APIs,
real-time delivery, and persistence of derived artifacts remain later steps.

## 7. Real-Time Event Delivery
- [ ] Add backend real-time event delivery
- [ ] Select SSE or WebSocket transport based on implementation needs
- [ ] Stream accepted live events to the frontend
- [ ] Stream generated alerts to the frontend
- [ ] Update device status in near real time
- [ ] Update timelines when relevant live events arrive
- [ ] Update dashboard metrics from validated backend data
- [ ] Handle temporary frontend/backend disconnections
- [ ] Add safe reconnect behaviour
- [ ] Ensure real-time delivery does not alter forensic calculations

## 8. Dashboard Results and Investigation APIs
- [ ] Create APIs for cases
- [ ] Create APIs for events
- [ ] Create APIs for alerts
- [ ] Create APIs for incidents
- [ ] Create APIs for timelines
- [ ] Create APIs for graphs and chart data
- [ ] Connect real analytical results to the dashboard
- [ ] Show risk breakdowns
- [ ] Show supporting evidence
- [ ] Show provenance/source references
- [ ] Add refresh controls
- [ ] Add reanalysis controls
- [ ] Allow historical review of previously captured live incidents

## 9. Visualization Engine + Qwen
- [ ] Create allowed visualization components
- [ ] Create and validate versioned layout JSON
- [ ] Allow only deterministic data references
- [ ] Let Qwen summarize validated results
- [ ] Let Qwen choose safe visualization layouts
- [ ] Reject unknown components and fields
- [ ] Reject invented numerical values
- [ ] Reject unsafe output
- [ ] Add deterministic fallback layouts
- [ ] Support visualization of both historical and live investigation data

## 10. AI Investigation Chat
- [ ] Add case-based chat
- [ ] Answer questions using selected evidence
- [ ] Explain alerts
- [ ] Explain risk scores
- [ ] Explain correlations
- [ ] Explain live incident sequences
- [ ] Return evidence references
- [ ] Save chat history
- [ ] Handle Qwen being offline

## 11. Alerts, Email, Reports and Automation
- [ ] Add SMTP setup
- [ ] Generate alert email drafts
- [ ] Support drafts for live detected incidents
- [ ] Require investigator approval before sending
- [ ] Add report export
- [ ] Auto-run analysis after batch upload
- [ ] Automatically process validated incoming live events
- [ ] Auto-group related alerts
- [ ] Create deterministic incident summaries before AI narration
- [ ] Preserve alert and notification audit history

## 12. Physical Live Demonstration
- [ ] Assemble the Arduino and IoT laboratory setup
- [ ] Verify normal device telemetry
- [ ] Verify live dashboard updates
- [ ] Execute a controlled simulated suspicious scenario
- [ ] Confirm the detection rule triggers
- [ ] Confirm a live alert appears
- [ ] Confirm the event is persisted as evidence
- [ ] Confirm the incident timeline updates
- [ ] Confirm device/entity relationships are visible
- [ ] Confirm the captured incident can be investigated after the live event
- [ ] Document the complete demonstration procedure

## Final Validation
- [ ] Test each phase
- [ ] Verify identical input produces identical forensic results
- [ ] Confirm live and batch events follow the same canonical pipeline
- [ ] Confirm Ollama does not affect forensic values
- [ ] Confirm Qwen being unavailable does not break core analysis
- [ ] Test malformed live telemetry
- [ ] Test temporary live connection loss
- [ ] Test controlled live alerting
- [ ] Prepare one complete batch demo case
- [ ] Prepare one complete live IoT demo case
- [ ] Complete setup documentation
- [ ] Complete hardware setup documentation
- [ ] Complete operator/demo instructions
