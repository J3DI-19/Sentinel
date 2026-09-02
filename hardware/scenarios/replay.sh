#!/usr/bin/env bash
# Capture one signed telemetry frame from the physical node and republish
# it. The backend accepts the frame (auth is valid, canonical shape is
# valid) but the receipt should flag a sequence regression because the
# sequence value has already been observed.
set -euo pipefail

: "${TV_MQTT_HOST:?set the broker host}"
: "${TV_MQTT_PORT:=8883}"
: "${TV_SOURCE_ID:?set the physical source id}"

TOPIC="tv/dev/${TV_SOURCE_ID}/telemetry"
CAPTURE="$(mktemp -t traceveil-replay.XXXXXX.json)"
trap 'rm -f "$CAPTURE"' EXIT

echo "capturing one frame from $TOPIC ..."
mosquitto_sub -h "$TV_MQTT_HOST" -p "$TV_MQTT_PORT" --cafile /etc/mosquitto/ca/traceveil-lab-ca.crt \
  -t "$TOPIC" -C 1 > "$CAPTURE"

echo "captured $(wc -c < "$CAPTURE") bytes; republishing (replay) ..."
mosquitto_pub -h "$TV_MQTT_HOST" -p "$TV_MQTT_PORT" --cafile /etc/mosquitto/ca/traceveil-lab-ca.crt \
  -t "$TOPIC" -f "$CAPTURE" -q 1

echo "done. Check /api/v1/cases/<id>/audit for a sequence_regression flag."
