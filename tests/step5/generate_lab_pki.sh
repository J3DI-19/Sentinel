#!/usr/bin/env bash
# Generate a throwaway lab CA and a set of client certs used by the
# Step 5 integration jobs. All output goes under tests/step5/pki/.
set -euo pipefail
cd "$(dirname "$0")"

OUT=./pki
mkdir -p "$OUT"

# CA
openssl req -x509 -newkey rsa:2048 -sha256 -nodes -days 2 \
  -subj "/CN=traceveil-lab-ca" \
  -keyout "$OUT/ca.key" -out "$OUT/ca.crt"

# Broker. A SubjectAltName carrying the IP is required: modern TLS
# stacks (Python's ssl) verify the connect address against the SAN and
# do NOT fall back to CN for IP addresses.
openssl req -newkey rsa:2048 -nodes -sha256 \
  -subj "/CN=127.0.0.1" \
  -keyout "$OUT/broker.key" -out "$OUT/broker.csr"
openssl x509 -req -in "$OUT/broker.csr" -CA "$OUT/ca.crt" -CAkey "$OUT/ca.key" \
  -CAcreateserial -out "$OUT/broker.crt" -days 2 -sha256 \
  -extfile <(printf "subjectAltName=IP:127.0.0.1,DNS:localhost,DNS:traceveil.lab")

# Two device CNs plus the bridge, all signed by the same CA
for cn in esp32-lab-01 esp32-lab-02 tv-bridge; do
  openssl req -newkey rsa:2048 -nodes -sha256 \
    -subj "/CN=$cn" \
    -keyout "$OUT/$cn.key" -out "$OUT/$cn.csr"
  openssl x509 -req -in "$OUT/$cn.csr" -CA "$OUT/ca.crt" -CAkey "$OUT/ca.key" \
    -CAcreateserial -out "$OUT/$cn.crt" -days 2 -sha256
done

# One rogue CN signed by a DIFFERENT (untrusted) CA
openssl req -x509 -newkey rsa:2048 -nodes -sha256 -days 2 \
  -subj "/CN=untrusted-lab-ca" \
  -keyout "$OUT/rogue-ca.key" -out "$OUT/rogue-ca.crt"
openssl req -newkey rsa:2048 -nodes -sha256 \
  -subj "/CN=rogue-node" \
  -keyout "$OUT/rogue-node.key" -out "$OUT/rogue-node.csr"
openssl x509 -req -in "$OUT/rogue-node.csr" -CA "$OUT/rogue-ca.crt" -CAkey "$OUT/rogue-ca.key" \
  -CAcreateserial -out "$OUT/rogue-node.crt" -days 2 -sha256

echo "PKI generated under $OUT"
