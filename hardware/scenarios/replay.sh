#!/usr/bin/env bash
# TV5-11: Replay demonstration. The backend's dedupe key is
# (source_id, sequence); a previously accepted sequence returns the
# ORIGINAL receipt with duplicate=true rather than creating a new one
# with a sequence_regression flag. The scenario now asserts that
# behavior, which is the actual security-relevant property: replay is
# recognized and refused a second receipt.
set -euo pipefail

: "${TV_MQTT_HOST:?set the broker host}"
: "${TV_MQTT_PORT:=8883}"
: "${TV_SOURCE_ID:?set the physical source id}"
: "${TV_MQTT_CA_FILE:?set TV_MQTT_CA_FILE to the lab CA path}"
: "${TV_MQTT_CLIENT_CERT:?set TV_MQTT_CLIENT_CERT to the operator client cert}"
: "${TV_MQTT_CLIENT_KEY:?set TV_MQTT_CLIENT_KEY to the operator client key}"

TOPIC="tv/dev/${TV_SOURCE_ID}/telemetry"
CAPTURE="$(mktemp -t traceveil-replay.XXXXXX.json)"
trap 'rm -f "$CAPTURE"' EXIT

echo "capturing one frame from $TOPIC ..."
mosquitto_sub -h "$TV_MQTT_HOST" -p "$TV_MQTT_PORT" \
  --cafile "$TV_MQTT_CA_FILE" --cert "$TV_MQTT_CLIENT_CERT" --key "$TV_MQTT_CLIENT_KEY" \
  -t "$TOPIC" -C 1 > "$CAPTURE"

echo "captured $(wc -c < "$CAPTURE") bytes; republishing (replay) ..."
mosquitto_pub -h "$TV_MQTT_HOST" -p "$TV_MQTT_PORT" \
  --cafile "$TV_MQTT_CA_FILE" --cert "$TV_MQTT_CLIENT_CERT" --key "$TV_MQTT_CLIENT_KEY" \
  -t "$TOPIC" -f "$CAPTURE" -q 1

cat <<'MSG'

Expected result:
  * bridge logs one "forwarded" line for the replayed frame.
  * The backend returns the ORIGINAL receipt with duplicate=true (see
    the receipt at /api/v1/live/receipts/<receipt_id>) and no new
    canonical event is created.
  * The case's Events tab shows the original event only; the count of
    live events for that source_id does NOT increase.
  * Compare with a fresh sequence to prove the pipeline still accepts
    new frames from the same source.
MSG
