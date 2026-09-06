#!/usr/bin/env bash
# TV5-03 (re-review fix): deterministic, subscriber-based ACL check that
# uses the CORRECT certificate for each role.
#
# The earlier version subscribed as esp32-lab-02 to its own /telemetry,
# but the ACL only grants device CNs `read tv/dev/%u/ack` - a device may
# NOT read telemetry at all. The only CN allowed to read device
# telemetry is the bridge (`tv-bridge`). So the observer here is
# tv-bridge.
#
# Test:
#   1. Subscribe as tv-bridge to tv/dev/esp32-lab-02/telemetry
#      (bridge is authorized: `topic read tv/dev/+/telemetry`).
#   2. Publish as esp32-lab-01 to esp32-lab-02's topic -> ACL denies the
#      write (a device may only write its own %u topics); the bridge
#      subscriber receives NOTHING.
#   3. Publish as esp32-lab-02 to its own topic -> allowed; the same
#      bridge subscriber receives it.
# Done when the same subscriber observes the valid message but not the
# spoofed one.
set -euo pipefail
cd "$(dirname "$0")"

PKI=./pki
ARGS=(-h 127.0.0.1 -p 8883 --cafile "$PKI/ca.crt")
BRIDGE=(--cert "$PKI/tv-bridge.crt"    --key "$PKI/tv-bridge.key")
LAB01=(--cert "$PKI/esp32-lab-01.crt"  --key "$PKI/esp32-lab-01.key")
LAB02=(--cert "$PKI/esp32-lab-02.crt"  --key "$PKI/esp32-lab-02.key")
TOPIC='tv/dev/esp32-lab-02/telemetry'

for _ in $(seq 1 40); do
  if (echo > /dev/tcp/127.0.0.1/8883) 2>/dev/null; then break; fi
  sleep 0.25
done

SPOOF_CAP="$(mktemp)"; LEGIT_CAP="$(mktemp)"
trap 'rm -f "$SPOOF_CAP" "$LEGIT_CAP"' EXIT

# --- (1) bridge subscribes; (2) lab-01 attempts to spoof lab-02 --------------
timeout 3 mosquitto_sub "${ARGS[@]}" "${BRIDGE[@]}" -t "$TOPIC" -C 1 > "$SPOOF_CAP" &
SUB=$!
sleep 0.5
mosquitto_pub "${ARGS[@]}" "${LAB01[@]}" -t "$TOPIC" -m '{"attempted":"spoof"}' -q 1 || true
wait $SUB 2>/dev/null || true

if [ -s "$SPOOF_CAP" ]; then
  echo "FAIL: spoof from esp32-lab-01 reached esp32-lab-02's topic:" >&2
  cat "$SPOOF_CAP" >&2
  exit 1
fi
echo "OK: cross-CN publish denied by ACL (bridge subscriber saw nothing)"

# --- (3) legitimate publish from lab-02 reaches the same bridge subscriber ---
timeout 3 mosquitto_sub "${ARGS[@]}" "${BRIDGE[@]}" -t "$TOPIC" -C 1 > "$LEGIT_CAP" &
SUB=$!
sleep 0.5
mosquitto_pub "${ARGS[@]}" "${LAB02[@]}" -t "$TOPIC" -m '{"legit":true}' -q 1
wait $SUB 2>/dev/null || true

if ! grep -q '"legit":true' "$LEGIT_CAP"; then
  echo "FAIL: legitimate publish from esp32-lab-02 not delivered to bridge subscriber" >&2
  echo "capture: $(cat "$LEGIT_CAP")" >&2
  exit 1
fi
echo "OK: own-CN publish delivered to the bridge subscriber"
echo "OK: ACL blocks cross-CN and permits own-CN publishes"
