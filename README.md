# Sentinel

Sentinel is an AI-assisted smart-home IoT digital forensics and incident response platform. It is an academic prototype that turns heterogeneous IoT evidence into explainable alerts, risk scores, correlated events, reconstructed timelines, device graphs, and investigation-ready reports.

## What it does

- Ingests public IoT datasets and simulated smart-home incidents.
- Preserves evidence provenance, source hashes, adapter versions, and validation errors.
- Normalizes heterogeneous records into a canonical event model.
- Runs deterministic rules, behavioral baselines, bounded risk scoring, correlation, and timeline reconstruction.
- Presents findings through a React dashboard with metrics, charts, evidence tables, timelines, and device graphs.
- Uses a local Qwen 9B Q4_K_M model through Ollama for evidence-grounded summaries, explanations, investigation chat, email drafts, and visualization layout planning.
- Exports reports and supports investigator-approved SMTP notifications.

Python remains the computational authority: the language model may explain validated results, but it cannot calculate forensic values, invent evidence, execute code, modify evidence, or send messages autonomously.

## Architecture

The platform is organized into these layers:

1. **Evidence and adapter layer** — registers cases, hashes inputs, validates dataset fields, and emits canonical events or documented rejections.
2. **Detection and risk engine** — applies rules and baselines and returns condition traces, evidence references, and factorized scores.
3. **Correlation and timeline engine** — links events using declared entity keys and time windows and produces stable, reproducible chronologies.
4. **Graph and query engine** — calculates graph relationships, filters, aggregates, and chart-ready values.
5. **API, storage, and alerts** — provides FastAPI/Pydantic contracts, SQLite persistence, audit history, exports, and approved SMTP delivery.
6. **Visualization and AI** — renders allow-listed React components and provides bounded local assistance.

## Technology stack

- **Frontend:** React, Vite, Tailwind CSS, shadcn/ui, Recharts, React Flow
- **Backend:** Python, FastAPI, Pandas, NetworkX, Pydantic
- **Storage:** SQLite, with a repository boundary for future PostgreSQL support
- **Local AI:** Ollama with Qwen 9B Q4_K_M
- **Testing and tooling:** Pytest, Git, GitHub, SMTP, and a modern browser

## Data sources and evaluation

The synopsis identifies TON_IoT and CICIoT2023 as public benchmark sources, supplemented by controlled simulated cases. Evaluation is intended to measure normalization correctness, reproducibility, detection and correlation quality, visualization safety, usability, and performance under declared configurations.

Representative golden cases should preserve expected normalized records, rule matches, risk factors, correlation edges, and ordered timelines so reviewers can verify the full investigation path.

## Scope and safeguards

Sentinel covers batch imports, case management, deterministic analysis, dashboard review, local AI assistance, SQLite case history, SMTP alerts, and report export.

It does not claim production readiness, legal admissibility, live interception, firmware extraction, autonomous containment, or replacement of enterprise SIEM, IoT security, or forensic products. Evidence is processed locally where possible, model context is bounded, secrets stay outside the repository, and deterministic findings are kept distinct from AI-generated narrative.

## Requirements

- 64-bit quad-core processor
- 16 GB RAM minimum; 24–32 GB recommended for local inference
- 30 GB free SSD space
- Optional supported GPU for faster Ollama responses
- Python, Node.js, SQLite, Git, and Ollama with the selected model

## Project documents

- [Full project synopsis (DOCX)](docs/synopsis/Sentinel_Full_Synopsis.docx)
- [Full project synopsis (PDF)](docs/synopsis/Sentinel_Full_Synopsis.pdf)

## Team

- Atharva Rangnekar (K053)
- Aarya Rao (K054)
- Ayra Jha (K028)
- Project guide: Prof. Rohit Suryawanshi

## Project status

The project is in the planning and documentation phase, with the implementation roadmap organized into progressive milestones:

1. **Foundation** — establish the React/Vite frontend, FastAPI backend, SQLite storage, shared contracts, and local Ollama/Qwen setup.
2. **Evidence pipeline** — add upload validation, hashing, canonical event normalization, and adapters for simulated data, TON_IoT, and CICIoT2023.
3. **Deterministic investigation** — implement filtering, stable sorting, detection rules, risk scoring, event correlation, timelines, graphs, and chart data.
4. **Investigator dashboard** — connect live APIs to case pages, results views, evidence tables, visualizations, risk breakdowns, and reanalysis controls.
5. **Bounded AI and delivery** — add allow-listed visualization layouts, evidence-grounded Qwen assistance, case chat, approved email drafts, report export, and offline fallbacks.
6. **Validation** — test each phase, verify reproducibility, confirm AI cannot alter forensic values, and prepare a complete demonstration case with setup and usage documentation.

The current repository provides the synopsis and roadmap baseline. Implementation will proceed from the foundation through the evidence pipeline and deterministic analytics before integrating the dashboard and local AI capabilities.
