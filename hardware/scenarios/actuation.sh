#!/usr/bin/env bash
# Physical procedure: with the ESP32 powered, use a jumper to briefly
# short GPIO 26 to 3V3 for ~200 ms. The relay coil energises without the
# node having emitted a preceding "command" event, so the next telemetry
# frame carries metrics.relay="on" while no command exists in the
# incident timeline. The correlator flags the ungrounded state change.
#
# This script prints the operator prompt and tails the live SSE stream so
# the effect is visible in near real time.
set -euo pipefail

: "${TV_API_BASE:=http://127.0.0.1:8000/api/v1}"
: "${TV_CASE_ID:?set the case id}"

cat <<'MSG'
Bench step:
  1. Confirm the relay is currently OFF in the live dashboard.
  2. Briefly bridge GPIO 26 to 3V3 with a jumper.
  3. Watch for a device_state or telemetry frame where relay="on" appears
     with no preceding command event in the case timeline.

Tailing live/stream (Ctrl+C to stop):
MSG

exec curl -N -sS "$TV_API_BASE/live/stream?case_id=${TV_CASE_ID}&topics=events,alerts"
