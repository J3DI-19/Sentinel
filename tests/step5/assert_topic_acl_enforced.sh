#!/usr/bin/env bash
# TV5-03: an esp32-lab-01 client must NOT be able to publish under
# tv/dev/esp32-lab-02/telemetry. mosquitto returns 0 from mosquitto_pub
# even if the broker later rejects the publish, so we assert on the
# broker log line instead.
set -euo pipefail
cd "$(dirname "$0")"

# Give the broker a moment to bind.
for _ in $(seq 1 40); do
  if (echo > /dev/tcp/127.0.0.1/8883) 2>/dev/null; then break; fi
  sleep 0.25
done

# Baseline: publishing under our own CN succeeds.
mosquitto_pub -h 127.0.0.1 -p 8883 \
  --cafile ./pki/ca.crt --cert ./pki/esp32-lab-01.crt --key ./pki/esp32-lab-01.key \
  -t tv/dev/esp32-lab-01/telemetry -m '{"schema_version":"1.0"}' -q 1

# Violation: same client tries to publish under lab-02. mosquitto_pub
# often exits 0; grep the debug log for the deny.
mosquitto_pub -h 127.0.0.1 -p 8883 \
  --cafile ./pki/ca.crt --cert ./pki/esp32-lab-01.crt --key ./pki/esp32-lab-01.key \
  -t tv/dev/esp32-lab-02/telemetry -m '{"schema_version":"1.0"}' -q 1 || true

# Depending on mosquitto version the deny message varies; sample the
# common phrasings.
sleep 0.5
if journalctl --no-pager -q -u mosquitto 2>/dev/null | grep -Ei 'denied|not authori[sz]ed' >/dev/null; then
  echo "OK: broker denied cross-CN publish (journalctl)"
  exit 0
fi

# Fallback: mosquitto in the foreground writes to stderr; the CI job
# redirects the broker output to a file when start_broker.sh is
# launched with & in a real workflow. Consult that if available.
if [ -f mosquitto.ci.log ] && grep -Ei 'denied|not authori[sz]ed' mosquitto.ci.log >/dev/null; then
  echo "OK: broker denied cross-CN publish (log file)"
  exit 0
fi

echo "FAIL: no deny record found in broker output" >&2
exit 1
