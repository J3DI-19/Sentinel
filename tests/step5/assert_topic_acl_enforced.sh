#!/usr/bin/env bash
# Re-review fix: deterministic, subscriber-based ACL enforcement check.
#
# The previous version grepped mosquitto's log for "denied" text and
# was fragile because the phrasing varies by version and log level.
# This version proves the ACL directly by watching whether a spoofed
# publish reaches a legitimate subscriber - a message-delivery signal,
# not a text signal.
#
# Test:
#   1. Subscribe as esp32-lab-02 to tv/dev/esp32-lab-02/telemetry.
#   2. Publish as esp32-lab-01 to tv/dev/esp32-lab-02/telemetry.
#   3. Assert the subscriber received NOTHING (broker refused).
#   4. Positive control: publish as esp32-lab-02 to its own topic;
#      assert the subscriber DOES receive that message.
set -euo pipefail
cd "$(dirname "$0")"

PKI=./pki
BROKER_ARGS=(-h 127.0.0.1 -p 8883 --cafile "$PKI/ca.crt")

# Wait for the broker to bind (started with & in the workflow).
for _ in $(seq 1 40); do
  if (echo > /dev/tcp/127.0.0.1/8883) 2>/dev/null; then break; fi
  sleep 0.25
done

SPOOF_CAP="$(mktemp)"
LEGIT_CAP="$(mktemp)"
trap 'rm -f "$SPOOF_CAP" "$LEGIT_CAP"' EXIT

# --- (1) subscribe as lab-02 --------------------------------------------------
timeout 3 mosquitto_sub "${BROKER_ARGS[@]}" \
  --cert "$PKI/esp32-lab-02.crt" --key "$PKI/esp32-lab-02.key" \
  -t 'tv/dev/esp32-lab-02/telemetry' -C 1 > "$SPOOF_CAP" &
SUB_PID=$!
sleep 0.5  # let the subscription register with the broker

# --- (2) attempted spoof from lab-01 -----------------------------------------
mosquitto_pub "${BROKER_ARGS[@]}" \
  --cert "$PKI/esp32-lab-01.crt" --key "$PKI/esp32-lab-01.key" \
  -t 'tv/dev/esp32-lab-02/telemetry' -m '{"attempted":"spoof"}' -q 1 || true

wait $SUB_PID 2>/dev/null || true

# --- (3) spoof must not have arrived -----------------------------------------
if [ -s "$SPOOF_CAP" ]; then
  echo "FAIL: spoof publish from esp32-lab-01 reached esp32-lab-02's topic:" >&2
  cat "$SPOOF_CAP" >&2
  exit 1
fi
echo "OK: cross-CN publish refused by broker (no message delivered)"

# --- (4) positive control ----------------------------------------------------
timeout 3 mosquitto_sub "${BROKER_ARGS[@]}" \
  --cert "$PKI/esp32-lab-02.crt" --key "$PKI/esp32-lab-02.key" \
  -t 'tv/dev/esp32-lab-02/telemetry' -C 1 > "$LEGIT_CAP" &
SUB_PID=$!
sleep 0.5

mosquitto_pub "${BROKER_ARGS[@]}" \
  --cert "$PKI/esp32-lab-02.crt" --key "$PKI/esp32-lab-02.key" \
  -t 'tv/dev/esp32-lab-02/telemetry' -m '{"legit":true}' -q 1

wait $SUB_PID 2>/dev/null || true

if ! grep -q '"legit":true' "$LEGIT_CAP"; then
  echo "FAIL: legitimate publish from esp32-lab-02 was not delivered" >&2
  echo "capture: $(cat "$LEGIT_CAP")" >&2
  exit 1
fi
echo "OK: legitimate publish under own CN was delivered"
echo "OK: ACL blocks cross-CN and permits own-CN publishes"
