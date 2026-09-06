#!/usr/bin/env bash
# Capture one frame, mutate a metric, and republish. The canonical event
# contract forbids unknown fields and refuses non-finite metrics; even for
# valid mutations, the sequence check flags a regression. This scenario
# demonstrates that tampering leaves an auditable trail without ever
# becoming an accepted canonical event.
set -euo pipefail

: "${TV_MQTT_HOST:?set the broker host}"
: "${TV_MQTT_PORT:=8883}"
: "${TV_SOURCE_ID:?set the physical source id}"

TOPIC="tv/dev/${TV_SOURCE_ID}/telemetry"
CAPTURE="$(mktemp -t traceveil-capture.XXXXXX.json)"
TAMPERED="$(mktemp -t traceveil-tamper.XXXXXX.json)"
trap 'rm -f "$CAPTURE" "$TAMPERED"' EXIT

mosquitto_sub -h "$TV_MQTT_HOST" -p "$TV_MQTT_PORT" --cafile /etc/mosquitto/ca/traceveil-lab-ca.crt \
  -t "$TOPIC" -C 1 > "$CAPTURE"

# Inject a metric name outside the allowed identifier regex.
python3 -c "
import json, sys
p = json.load(open('$CAPTURE'))
p.setdefault('metrics', {})['not a valid metric name'] = 1
json.dump(p, open('$TAMPERED','w'))
"

mosquitto_pub -h "$TV_MQTT_HOST" -p "$TV_MQTT_PORT" --cafile /etc/mosquitto/ca/traceveil-lab-ca.crt \
  -t "$TOPIC" -f "$TAMPERED" -q 1

echo "done. Expect a row in live_ingest_issues with reason=malformed_live_telemetry."
