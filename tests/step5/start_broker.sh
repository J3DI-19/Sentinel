#!/usr/bin/env bash
# Boots mosquitto with the lab PKI and the traceveil ACL for the CI job.
set -euo pipefail
cd "$(dirname "$0")"

CONF=./mosquitto.ci.conf
cat > "$CONF" <<CONF
listener 8883 127.0.0.1
cafile   $(pwd)/pki/ca.crt
certfile $(pwd)/pki/broker.crt
keyfile  $(pwd)/pki/broker.key
require_certificate true
use_identity_as_username true
allow_anonymous false
acl_file $(pwd)/../../hardware/mqtt_bridge/traceveil.acl
log_type notice
log_type warning
log_type error
persistence false
CONF

exec mosquitto -c "$CONF" -v
