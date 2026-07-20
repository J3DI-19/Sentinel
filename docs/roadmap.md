# Traceveil Roadmap

## 1. Initialization
- [x] Set up React + Vite frontend
- [x] Set up FastAPI backend
- [x] Set up SQLite
- [x] Install required libraries
- [x] Connect frontend and backend
- [x] Add Ollama configuration and optional availability/model health checks
- [ ] Install Ollama, pull the selected Qwen 9B Q4_K_M model, and verify it locally

**Current result:** The Traceveil frontend status shell connects to FastAPI and
reports API, SQLite, and optional Ollama health. Backend health tests pass (4
tests), and the frontend test and production build pass (1 test). Traceveil
remains usable when Ollama is offline.

## 2. Frontend and Investigation Interface
- [x] Build the initial Step 1 service-status shell
- [ ] Build the global application layout and navigation
- [ ] Build case pages
- [ ] Build evidence upload/import page
- [ ] Build main investigation dashboard
- [ ] Add metric and severity cards
- [ ] Add evidence tables
- [ ] Add chart placeholders
- [ ] Add incident timeline placeholder
- [ ] Add device/entity graph placeholder
- [ ] Add recommendations/findings panels
- [ ] Add live monitoring status indicators
- [ ] Add live event feed
- [ ] Add live alert feed
- [ ] Add device connection/status components
- [ ] Add chat section
- [ ] Add email/report sections
- [ ] Use structured mock data before backend feature integration

**Current result:** The existing frontend remains an initialization/status shell
only. The case, investigation, visualization, live-monitoring, chat, email, and
report interfaces are planned but not implemented.

## 3. Input Check and Evidence Validation
- [ ] Accept supported evidence file types
- [ ] Check file size and structure
- [ ] Validate required columns
- [ ] Detect missing or invalid values
- [ ] Hash and store evidence metadata
- [ ] Preserve source metadata
- [ ] Show validation errors
- [ ] Define validated live telemetry input contracts
- [ ] Validate incoming device identifiers and event types
- [ ] Reject malformed live telemetry
- [ ] Record live ingestion timestamps
- [ ] Preserve source/device provenance for live evidence

## 4. Canonical Event Model and Normalization
- [ ] Create the common canonical event schema
- [ ] Map simulated data
- [ ] Map TON_IoT data
- [ ] Map CICIoT2023 data
- [ ] Standardize timestamps
- [ ] Standardize device and entity fields
- [ ] Preserve source row references
- [ ] Create a live telemetry adapter
- [ ] Normalize live device events into the canonical event model
- [ ] Preserve live source and ingestion metadata

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
- [ ] Add deterministic filters
- [ ] Add stable sorting
- [ ] Add detection rules
- [ ] Add behavioural baselines
- [ ] Add bounded risk scoring
- [ ] Add event correlation
- [ ] Build incident timelines
- [ ] Generate graph data
- [ ] Generate chart-ready aggregates
- [ ] Support analysis of both batch and live events
- [ ] Trigger alerts from qualifying live events

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
