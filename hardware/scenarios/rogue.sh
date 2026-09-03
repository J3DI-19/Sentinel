#!/usr/bin/env bash
# Publish a syntactically valid frame under a source_id that has no entry
# in LIVE_SOURCE_TOKENS. verify_source rejects it; the frame never becomes
# evidence, but the rejection is audited.
set -euo pipefail

: "${TV_API_BASE:=http://127.0.0.1:8000/api/v1}"
: "${TV_CASE_ID:?set the case id}"

ROGUE_ID="rogue-node-01"
NOW="$(date -u +%Y-%m-%dT%H:%M:%S.000+00:00)"

curl -sS -X POST "$TV_API_BASE/live/telemetry" \
  -H "Content-Type: application/json" \
  -H "X-Traceveil-Source-Token: not-a-registered-token" \
  --data @- <<JSON
{
  "schema_version": "1.0",
  "case_id": ${TV_CASE_ID},
  "source_id": "${ROGUE_ID}",
  "device_id": "${ROGUE_ID}",
  "event_type": "telemetry",
  "observed_at": "${NOW}",
  "sequence": 0,
  "metrics": {"temperature_c": 22.0}
}
JSON

echo
echo "Expect HTTP 403 invalid_live_source_token; audit tab shows the rejection."
