# Traceveil

**Traceveil: AI-Assisted Real-Time Smart Home IoT Digital Forensics and Incident Response Platform** is a final-year academic prototype that combines historical/batch IoT evidence analysis with controlled real-time IoT telemetry monitoring and alerting. It is designed to turn heterogeneous records into explainable alerts, risk scores, correlated events, reconstructed timelines, device/entity graphs, and investigation-ready reports without presenting itself as a production IDS or SIEM.

## What it does

Traceveil is planned to:

- Ingest public IoT datasets, simulated incidents, and uploaded evidence files.
- Receive live telemetry from an Arduino-compatible microcontroller and IoT test device in an authorized laboratory setup.
- Normalize batch and live records into one canonical event model while preserving source, device, ingestion, and raw-record provenance.
- Apply deterministic rules, behavioural baselines, bounded risk scoring, event correlation, and timeline reconstruction.
- Generate device/entity relationships, chart-ready aggregates, and live alerts from verified backend values.
- Preserve accepted live events as evidence for later forensic investigation.
- Present historical and incoming findings through a React investigation dashboard.
- Use a local Qwen 9B Q4_K_M model through Ollama only for evidence-grounded summaries, explanations, investigation chat, email drafts, and visualization layout planning.

Python remains the computational authority. The language model may explain validated results, but it cannot calculate forensic values, create unsupported alerts, invent or alter evidence, execute attack logic, run arbitrary code, or send messages autonomously. Alerting, scoring, detection, correlation, timelines, graphs, and chart values remain deterministic for both ingestion paths.

## Architecture

Traceveil uses two input paths that converge before analysis:

```text
Batch Evidence -----\
                     -> Canonical Events -> Common Investigation Pipeline
Live IoT Events ----/
```

The platform is organized into these layers:

1. **Batch Evidence and Adapter Layer** — registers cases, hashes and validates uploaded evidence, and adapts simulated data, TON_IoT, and CICIoT2023 records.
2. **Live IoT Collection Layer** — receives controlled device telemetry, validates message structure and source identifiers, and records ingestion metadata. MQTT and/or HTTP will be selected during implementation.
3. **Canonical Event and Normalization Layer** — maps accepted batch and live inputs into one versioned event model with retained provenance.
4. **Detection and Risk Engine** — applies deterministic rules, behavioural baselines, and bounded factorized scores.
5. **Correlation and Timeline Engine** — links events through declared entity keys and time windows and produces stable, reproducible chronologies.
6. **Graph and Query Engine** — calculates device/entity relationships, filters, aggregates, and chart-ready values.
7. **API, Storage and Real-Time Event Delivery** — provides FastAPI/Pydantic contracts, SQLite persistence, audit history, exports, approved SMTP delivery, and planned SSE or WebSocket updates.
8. **Visualization and AI Layer** — renders allow-listed React components and provides bounded local assistance over validated evidence.
9. **React Investigation Dashboard** — presents cases, evidence, metrics, live status, event and alert feeds, timelines, graphs, charts, findings, chat, and reports.

The live path is not a separate analytics system. Accepted live telemetry passes through the same canonical model and deterministic investigation pipeline as batch evidence, then remains available for historical review.

## Technology stack

- **Frontend:** React, Vite, Tailwind CSS, shadcn/ui, Recharts, React Flow
- **Backend:** Python, FastAPI, Pandas, NetworkX, Pydantic
- **Storage:** SQLite, with a repository boundary for future PostgreSQL support
- **Local AI:** Ollama with Qwen 9B Q4_K_M
- **Planned live communication:** MQTT and/or HTTP for device telemetry; SSE or WebSockets for server-driven frontend updates
- **Testing and tooling:** Pytest, Vitest, Git, GitHub, SMTP, and a modern browser

No live communication protocol or supporting library has been selected or implemented yet.

## Data sources and evaluation

Traceveil uses TON_IoT and CICIoT2023 as public benchmark sources, supplemented by controlled simulated cases and a small authorized IoT laboratory demonstration. Evaluation will cover normalization correctness, reproducibility, detection and correlation quality, visualization safety, usability, live ingestion and delivery behaviour, and performance under declared hardware and network conditions.

Representative golden cases will preserve expected normalized records, rule matches, risk factors, correlation edges, and ordered timelines. Live evaluation will additionally cover valid and malformed telemetry, device/source identification, evidence persistence, temporary disconnections, reconnect behaviour, delivery latency, and a controlled suspicious-event scenario.

## Scope and safeguards

In scope are batch imports, case management, controlled laboratory live telemetry acquisition, deterministic analysis, near-real-time alerts, dashboard review, preservation of live events, local AI assistance, SQLite case history, investigator-approved SMTP alerts, and report export. The controlled demonstration may use repeated authentication failures, abnormal request frequency, unexpected command sequences, deliberate telemetry spikes, or simulated suspicious state changes against owned or authorized test devices.

Out of scope are production-scale IoT monitoring, passive interception of arbitrary third-party networks, unauthorized device access, firmware extraction, production fleet management, automated containment, autonomous attack execution, legal-admissibility claims, and replacement of enterprise SIEM or IoT security products. Evidence is processed locally where possible, model context is bounded, secrets remain outside the repository, and deterministic findings are kept distinct from AI-generated narrative.

## Requirements

### Development computer

- 64-bit quad-core processor
- 16 GB RAM minimum; 24–32 GB recommended for local inference
- 30 GB free SSD space
- Optional supported GPU for faster Ollama responses
- Python 3.11 or newer, Node.js 20 or newer, SQLite, Git, and Ollama with the selected model

### Controlled live demonstration

- Arduino-compatible microcontroller
- At least one IoT test device or controllable IoT endpoint
- Local network or Wi-Fi environment
- Supporting data cables and power as required by the selected hardware

Exact hardware and communication protocols remain implementation decisions.

## Project documents

- [Full project synopsis (DOCX)](docs/synopsis/Traceveil_Full_Synopsis.docx)
- [Full project synopsis (PDF)](docs/synopsis/Traceveil_Full_Synopsis.pdf)
- [Implementation roadmap](docs/roadmap.md)

## Team

- Atharva Rangnekar (K053)
- Aarya Rao (K054)
- Ayra Jha (K028)
- Project guide: Prof. Rohit Suryawanshi

## Project status

Steps 1 through 4 and Step 6 are complete. The repository contains the React/Vite application shell, FastAPI health endpoints, SQLite initialization, frontend/backend connectivity, dependency manifests, tests, local Ollama/Qwen setup, backend evidence validation, the versioned canonical event/normalization pipeline, and the deterministic investigation engine. The frontend includes navigation, case workspaces, evidence import, investigation dashboards, deterministic visualization placeholders, timelines, entity graphs, findings, live-monitoring views, the Investigation Assistant, and report review flows.

Step 2 interfaces currently operate on structured mock data. Step 3 supplies deterministic validation and the shared live-telemetry input contract. Step 4 maps simulated, TON_IoT, CICIoT2023, generic, and accepted live inputs into one strict canonical schema with deterministic identifiers and complete source provenance. Step 6 applies versioned filters, stable sorting, rules, behavioural baselines, bounded factorized scoring, correlation, incidents, timelines, graphs, aggregates, and live-trigger alert creation. Live collection, real-time delivery, investigation APIs, production AI integration, automation, and the physical demonstration remain planned work. See the [validation contract](docs/contracts/evidence-validation.md), [canonical event contract](docs/contracts/canonical-event.md), [deterministic analysis contract](docs/contracts/deterministic-analysis.md), and [roadmap](docs/roadmap.md).

Implementation can now proceed with Step 5 live collection, Step 7 real-time delivery, and Step 8 investigation APIs against the finalized validation, canonical-event, and deterministic-analysis contracts.

## Step 1 setup and run

Step 1 provides the initialization foundation only: FastAPI health APIs, minimal SQLite initialization, a React/Vite status shell, and optional Ollama availability detection. Evidence ingestion, analytics, authentication, investigation features, and live IoT monitoring are not included yet.

### Prerequisites

- Python 3.11 or newer
- Node.js 20 or newer and npm
- Optional: Ollama for local Qwen availability checks

From the repository root, create the local environment file:

```powershell
Copy-Item .env.example backend\.env
```

### Backend installation and tests

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
```

Start the backend from `backend/`:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Health endpoints are available at:

- `http://127.0.0.1:8000/api/v1/health`
- `http://127.0.0.1:8000/api/v1/health/db`
- `http://127.0.0.1:8000/api/v1/health/ai`

### Frontend installation and tests

In a second terminal from the repository root:

```powershell
cd frontend
npm install
npm test
npm run build
npm run dev
```

Open `http://localhost:5173`. The Vite proxy forwards `/api` requests to the backend at `http://127.0.0.1:8000`.

### Optional Ollama setup

Install Ollama separately, start its local service, and pull the selected Qwen 9B Q4_K_M model. Set the exact installed model name in `backend\.env` as `OLLAMA_MODEL`. Then check:

```powershell
ollama list
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/ai
```

If Ollama is not installed or stopped, the AI health endpoint returns an unavailable optional status while the API, SQLite, and frontend continue to work.
