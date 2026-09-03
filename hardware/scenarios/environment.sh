#!/usr/bin/env bash
# Physical procedure: warm the DHT22 sensor above TV_TEMP_C_ALERT_ABOVE
# (default 32 C) with a hair dryer at low speed for ~20 seconds. The node
# emits normal telemetry frames; because temperature crosses the threshold
# the sketch also sets metrics.threshold_over_temp = true, which the
# environment detection rule picks up.
#
# This script only tails the live SSE stream so an operator can visually
# confirm the anomaly. It never fabricates events - real telemetry drives
# the demonstration.
set -euo pipefail

: "${TV_API_BASE:=http://127.0.0.1:8000/api/v1}"
: "${TV_CASE_ID:?set the case id}"

echo "Warming the DHT22 with a hair dryer at low speed."
echo "Tailing live/stream for the case (Ctrl+C when the alert fires):"
exec curl -N -sS "$TV_API_BASE/live/stream?case_id=${TV_CASE_ID}&topics=events,alerts"
