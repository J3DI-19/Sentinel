#!/usr/bin/env bash
# TV5-02: a certificate signed by a CA the broker does not trust must be
# refused. mosquitto_pub exits non-zero when the broker rejects the TLS
# handshake; we treat that as success.
set -euo pipefail
cd "$(dirname "$0")"

# Give the broker a moment to bind.
for _ in $(seq 1 40); do
  if (echo > /dev/tcp/127.0.0.1/8883) 2>/dev/null; then break; fi
  sleep 0.25
done

set +e
mosquitto_pub -h 127.0.0.1 -p 8883 \
  --cafile ./pki/ca.crt \
  --cert   ./pki/rogue-node.crt \
  --key    ./pki/rogue-node.key \
  -t tv/dev/rogue-node/telemetry -m 'hello' -q 1
rc=$?
set -e

if [ $rc -eq 0 ]; then
  echo "FAIL: broker accepted a client cert signed by an untrusted CA" >&2
  exit 1
fi
echo "OK: untrusted client rejected (rc=$rc)"
