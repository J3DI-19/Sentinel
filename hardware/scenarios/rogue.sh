#!/usr/bin/env bash
# TV5-12: Rogue-device demonstration. The backend's live collector
# authenticates the source before recording the request in
# live_ingest_issues, so an INVALID token produces:
#   * HTTP 401 from POST /api/v1/live/telemetry, AND
#   * a uvicorn access-log line for the failed request, AND
#   * NO row in live_ingest_issues, NO row in audit_events, NO evidence.
#
# The absence of an audit record for a rejected token is intentional at
# the current backend: verify_source raises before the endpoint reaches
# record_malformed(), so no attacker-controlled bytes touch the audit
# table. If your case demands an explicit audit row for
# authentication-failure, that requires a backend change (adding a safe,
# rate-limited, non-sensitive audit event to verify_source) which is
# tracked outside Step 5. This scenario therefore asserts the observable
# signals that DO exist today.
set -euo pipefail

: "${TV_API_BASE:=http://127.0.0.1:8000/api/v1}"
: "${TV_CASE_ID:?set the case id}"

ROGUE_ID="rogue-node-01"
NOW="$(date -u +%Y-%m-%dT%H:%M:%S.000+00:00)"

echo "sending frame with an unregistered token; expect HTTP 401..."
curl -sS -o /dev/null -w "http_status=%{http_code}\n" \
  -X POST "$TV_API_BASE/live/telemetry" \
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

cat <<'MSG'

Expected:
  * http_status=401.
  * The uvicorn access log shows the rejected request.
  * GET /api/v1/cases/${TV_CASE_ID}/events?origin=live returns no new event.
  * GET /api/v1/cases/${TV_CASE_ID}/audit shows no new audit row (this is
    intentional; see the header of this script for why).
  * The bridge is not exercised in this scenario (frame is sent directly
    to HTTP), so bridge logs and the spool depth are unchanged.
MSG
