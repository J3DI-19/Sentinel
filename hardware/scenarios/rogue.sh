#!/usr/bin/env bash
# TV5-12: Rogue-device demonstration. The backend rejects the frame at
# the auth boundary and now writes a bounded, structured audit row.
#
#   * HTTP 401 from POST /api/v1/live/telemetry
#   * a uvicorn access-log line for the failed request
#   * NO row in live_ingest_issues, NO canonical event, NO receipt
#   * ONE row in audit_events with action="live.auth_failure", details
#     including reason="invalid_token", the source_id if it was a valid
#     identifier (or "invalid_format" if it wasn't), and client_ip
#   * The presented token is NEVER stored (secret hygiene) and
#     attacker-controlled source_id strings that don't match the safe
#     identifier regex are recorded as "invalid_format" instead of
#     verbatim
#   * Repeated attempts from the same source_id or client_ip are
#     rate-limited to LIVE_AUTH_FAILURE_AUDIT_PER_MINUTE (default 6)
#     rows/minute so a brute-force flood cannot fill audit_events
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
  * The audit_events table has ONE new row with:
      action        = "live.auth_failure"
      actor         = "system"
      subject_type  = "live_source"
      details.reason      = "invalid_token"
      details.source_id   = "rogue-node-01"   (would be "invalid_format"
                                               if the source_id string
                                               did not match the safe
                                               identifier regex)
      details.client_ip   = <remote address>
    Note: this row has case_id=NULL because the source is not attached
    to any active session. Query it directly with:
      sqlite3 data/traceveil.db "SELECT action, details_json FROM audit_events \
        WHERE action='live.auth_failure' ORDER BY occurred_at DESC LIMIT 5;"
  * The bridge is not exercised (frame goes directly to HTTP), so
    bridge logs and the spool depth are unchanged.
MSG
