# Sentinel Roadmap

## 1. Initialization
- [ ] Set up React + Vite frontend
- [ ] Set up FastAPI backend
- [ ] Set up SQLite
- [ ] Install required libraries
- [ ] Connect frontend and backend
- [ ] Set up Ollama + Qwen

## 2. Frontend
- [ ] Build navigation and case pages
- [ ] Build upload page
- [ ] Build dashboard
- [ ] Add tables, charts, timeline and graph placeholders
- [ ] Add chat and email sections
- [ ] Use mock data first

## 3. Input Check and Validation
- [ ] Accept supported file types
- [ ] Check file size and structure
- [ ] Validate required columns
- [ ] Detect missing or invalid values
- [ ] Hash and store evidence metadata
- [ ] Show validation errors

## 4. Normalization
- [ ] Create a common event schema
- [ ] Map simulated data
- [ ] Map TON_IoT data
- [ ] Map CICIoT2023 data
- [ ] Standardize timestamps and device fields
- [ ] Preserve source row references

## 5. Filtering, Sorting and Analysis
- [ ] Add filters and stable sorting
- [ ] Add detection rules
- [ ] Add risk scoring
- [ ] Add event correlation
- [ ] Build incident timelines
- [ ] Generate graph and chart data

## 6. Dashboard Results
- [ ] Create APIs for events, alerts and incidents
- [ ] Connect real results to the dashboard
- [ ] Show risk breakdowns
- [ ] Show supporting evidence
- [ ] Add refresh and reanalysis controls

## 7. Visual Engine + Qwen
- [ ] Create allowed visualization components
- [ ] Create and validate layout JSON
- [ ] Let Qwen summarize results
- [ ] Let Qwen choose safe layouts
- [ ] Reject invented values or unsafe output
- [ ] Add fallback layouts

## 8. AI Chat
- [ ] Add case-based chat
- [ ] Answer questions using selected evidence
- [ ] Explain alerts, scores and correlations
- [ ] Return evidence references
- [ ] Save chat history
- [ ] Handle Qwen being offline

## 9. Email, Reports and Automation
- [ ] Add SMTP setup
- [ ] Generate alert email drafts
- [ ] Require approval before sending
- [ ] Add report export
- [ ] Auto-run analysis after upload
- [ ] Auto-group alerts and create summaries

## Final Check
- [ ] Test each phase
- [ ] Verify the same input gives the same result
- [ ] Confirm Ollama does not affect forensic values
- [ ] Prepare one complete demo case
- [ ] Complete setup and usage documentation
