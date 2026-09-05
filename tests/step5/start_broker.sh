#!/usr/bin/env bash
# Boots mosquitto with the lab PKI and the traceveil ACL for the CI
# job. Re-review: log_type "all" is enabled so the workflow can capture
# a broker log to disk as a secondary signal. The primary ACL
# assertion is subscriber-based (see assert_topic_acl_enforced.sh) and
# does not depend on any log-level phrasing.
set -euo pipefail
cd "$(dirname "$0")"

CONF=./mosquitto.ci.conf
# Copy the ACL next to the conf so the path carries no "..", and the file
# sits in the (world-readable) CI workspace rather than being referenced
# across directories.
cp ../../hardware/mqtt_bridge/traceveil.acl ./traceveil.acl

cat > "$CONF" <<CONF
listener 8883 127.0.0.1
cafile   $(pwd)/pki/ca.crt
certfile $(pwd)/pki/broker.crt
keyfile  $(pwd)/pki/broker.key
require_certificate true
use_identity_as_username true
allow_anonymous false
acl_file $(pwd)/traceveil.acl
log_type all
persistence false
CONF

exec mosquitto -c "$CONF" -v
