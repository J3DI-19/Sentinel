#!/usr/bin/env bash
# Physical procedure: unplug or shield the ESP32 antenna for ~20 seconds.
# Broker LWT publishes {"status":"offline"} on tv/dev/{source_id}/status,
# which the bridge translates into a heartbeat event with link=lost. On
# reconnect the ESP32 announces {"status":"online"} and resumes telemetry.
# SSE clients replay from Last-Event-ID with no gap in the browser view.
set -euo pipefail

: "${TV_API_BASE:=http://127.0.0.1:8000/api/v1}"
: "${TV_CASE_ID:?set the case id}"

cat <<'MSG'
Bench step:
  1. Note the current live/stream cursor.
  2. Disconnect Wi-Fi to the ESP32 for ~20 seconds.
  3. Restore Wi-Fi and observe the reconnect from Last-Event-ID.

Tailing live/stream (Ctrl+C to stop):
MSG

exec curl -N -sS "$TV_API_BASE/live/stream?case_id=${TV_CASE_ID}&topics=events,alerts,heartbeat"
