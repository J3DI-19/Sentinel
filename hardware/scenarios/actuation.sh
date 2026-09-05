#!/usr/bin/env bash
# TV5-01 / TV5-06: SAFE unauthorized-actuation demonstration.
#
# The unsafe procedure (bridging GPIO 26 to 3.3 V) is REMOVED. GPIO 26 is
# an ESP32 output driven LOW by the sketch; forcing it to 3.3 V would
# create a short across the output driver and can permanently damage the
# board. Do not do it. Do not restore that instruction.
#
# The safe scenario relies on the wiring the sketch now assumes:
#
#   * GPIO 26 (TV_PIN_RELAY)        - output the sketch drives to command
#                                     the relay.
#   * GPIO 25 (TV_PIN_RELAY_SENSE)  - INPUT taken from the relay's
#                                     switched side (via a high-impedance
#                                     divider or opto-isolator, wired by
#                                     a qualified bench engineer). The
#                                     sketch reports this as metrics.relay.
#   * GPIO 33 (TV_PIN_COMMAND_BUTTON) - INPUT_PULLUP. Pressing it is the
#                                     authorized command path; the sketch
#                                     emits a "command" event AND toggles
#                                     the relay.
#
# Ungrounded state change (the case we want to catch) is created by
# physically flipping the relay from the load-side without pressing the
# button. Do this with a manual override switch on the isolator, not by
# tapping any GPIO. The sense pin sees the change; the sketch emits a
# device_state event; no matching command event precedes it; the
# correlator flags the ungrounded transition.
#
# This script tails the live SSE stream so the effect is visible in near
# real time. It never fabricates events - real device state drives the
# demonstration.
set -euo pipefail

: "${TV_API_BASE:=http://127.0.0.1:8000/api/v1}"
: "${TV_CASE_ID:?set the case id}"

cat <<'MSG'
Bench procedure (safe):
  1. Confirm the relay is currently OFF and the sketch shows metrics.relay="off"
     in the last telemetry frame in the dashboard.
  2. Using the ISOLATED manual override on the relay module (NOT any GPIO),
     flip the relay to the ON position. The sense pin picks up the change.
  3. Watch for a device_state frame with relay=true and confirm the case
     timeline has NO preceding "command" event for the relay.
  4. Reset by pressing the command button on the ESP32; a "command" event
     appears and the sketch drives the relay back OFF.

Tailing live/stream (Ctrl+C to stop):
MSG

exec curl -N -sS "$TV_API_BASE/live/stream?case_id=${TV_CASE_ID}&topics=events,alerts"
