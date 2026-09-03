# Step 5 - Live IoT Integration

Phase 3 completed the software-only live path: `POST /api/v1/live/telemetry`
authenticates with `X-Traceveil-Source-Token`, validates
`LiveTelemetryInput`, issues a durable receipt, normalizes into a
canonical event, and forwards to the deterministic analysis pipeline
that Step 6 owns. Step 5 adds the **physical device** and an **optional
MQTT transport** without changing that contract; the simulator
(`backend/simulate_live.py`) remains the acceptance surrogate and the
hardware node must behave identically on the wire.

This document reflects the PR #8 review outcome. Security-relevant
requirements are marked with their finding id (TV5-XX).

## Hardware selection

| Item | Choice | Why |
| --- | --- | --- |
| Microcontroller | ESP32-WROOM-32 dev kit | Onboard Wi-Fi + TLS, dual core, mature Arduino core. |
| Environment sensor | DHT22 (AM2302) on GPIO 4 | One-wire temperature and humidity. |
| Motion sensor | HC-SR501 PIR on GPIO 27 | Digital `device_state` transitions. |
| Actuator | Single-channel 5 V relay on GPIO 26 | Emits `command` and `device_state` events. |
| Relay sense (TV5-06) | High-impedance / opto-isolated tap on GPIO 25 (INPUT) | Reads back the actual switched state of the relay so `metrics.relay` reflects reality, not a cached command. |
| Command button (TV5-06) | Momentary switch on GPIO 33 (INPUT_PULLUP) | Authorized command path - pressing it emits a `command` event and toggles the relay. |
| Status LED | Onboard GPIO 2 | Solid = Wi-Fi up, off = offline, blinking = halt state. |
| Power | 5 V USB from the demo laptop | Keeps the node on the same isolated bench as the AP. |

**GPIO safety (TV5-01).** The sketch drives GPIO 26 as OUTPUT. Never
short an output pin to a supply rail; instead observe the relay state
through the isolated sense pin and drive commands through the button or
the sketch. The old actuation procedure that told the operator to
bridge GPIO 26 to 3V3 is REMOVED and must not be reintroduced.

## Controlled laboratory topology

```
[ESP32 sensor node] ---Wi-Fi (WPA2)--- [Lab AP / isolated VLAN]
                                            |
             (no default route; explicit egress rule for local NTP only)
                                            |
              +-----------------------------+-----------------------------+
              |                                                           |
              v                                                           v
   [ mosquitto broker :8883 ]                              [ FastAPI :8443 /api/v1 ]
   tv/dev/{source_id}/telemetry                             live/telemetry
   tv/dev/{source_id}/status  (retained LWT)                (X-Traceveil-Source-Token, HTTPS)
   tv/dev/{source_id}/ack                                   cases/{case_id}/live-sessions
              |                                                           ^
              v                                                           |
   [ hardware/mqtt_bridge/bridge.py ] ---HTTPS---> POSTs each frame ------+
        (SQLite spool + backoff)
```

Rules for the lab environment:

- The AP is on its own VLAN with no default route. NTP is either a
  local server on the lab network or a controlled outbound UDP 123
  egress rule; see TV5-04 below.
- The broker on the host is bound to the **explicit lab interface
  address**, not `0.0.0.0` (TV5-05). Host firewall admits only the
  ESP32 subnet.
- The Traceveil source token is provisioned via `LIVE_SOURCE_TOKENS` in
  `backend/.env` (JSON object, one token per `source_id`) and flashed
  onto the ESP32 via `config.h`. Tokens never appear in git history.
- The broker uses `mosquitto` with client-certificate auth on port
  8883, an ACL file that pins each certificate CN to its own device
  topics (TV5-03), and anonymous access disabled.
- Every node has its own client certificate whose CN equals its
  `TV_SOURCE_ID`; the bridge has its own client certificate with CN
  `tv-bridge`.
- Time is synchronized on both the ESP32 and the FastAPI host. The
  sketch **refuses to publish** until NTP has produced a plausibly
  recent UTC clock (TV5-04).

## Live telemetry message format

Step 5 emits exactly the existing `LiveTelemetryInput` contract
(`backend/app/evidence/schemas.py`):

```json
{
  "schema_version": "1.0",
  "case_id": 1,
  "source_id": "esp32-lab-01",
  "device_id": "esp32-lab-01",
  "event_type": "telemetry",
  "observed_at": "2026-09-02T10:14:22.318+00:00",
  "sequence": 4213,
  "metrics": {
    "temperature_c": 24.7,
    "humidity_pct": 41.2,
    "motion": false,
    "relay": "off",
    "battery_voltage": 4.82
  }
}
```

Additional rules the hardware node observes:

- `event_type` is one of `telemetry | device_state | authentication |
  network | command | heartbeat`. Motion transitions send
  `device_state`; **observed** relay transitions send `device_state`;
  authorized button-driven relay toggles send `command`; periodic
  keepalives send `heartbeat`.
- `sequence` is strictly monotonic per (`source_id`, boot). It is
  stored in ESP32 NVS so it survives a reset. A regression is
  recognized by the backend as a **duplicate** replay (dedupe key is
  `(source_id, sequence)`) - see TV5-11 in
  `docs/step-5-testing.md`.
- `observed_at` is set from the local NTP-synced clock in UTC. If NTP
  has not produced a plausible clock, the node halts and does not
  publish.
- `metrics` keys match `^[A-Za-z0-9._:-]+$` and values are finite
  scalars.

MQTT topics (only when the MQTT bridge is used):

- `tv/dev/{source_id}/telemetry` - device -> bridge, QoS 0 (see below).
- `tv/dev/{source_id}/status` - retained LWT payload
  `{"status":"offline"}` set on connect; the node publishes
  `{"status":"online"}` immediately after a successful subscribe. The
  bridge maps status transitions to `heartbeat` events.
- `tv/dev/{source_id}/ack` - bridge -> device, QoS 1. Payload
  `{"sequence": N}` is published after the backend accepts frame N.
  The sketch clears N from its unacked ring buffer on receipt.

**MQTT QoS and delivery guarantees (TV5-08, TV5-09).** PubSubClient
publishes at **QoS 0**. Step 5 does NOT claim QoS 1 on the MQTT hop.
Delivery is instead guaranteed end-to-end by three cooperating
mechanisms:

1. The sketch keeps a bounded RAM ring buffer (`TV_ACK_BUFFER_SIZE`)
   of frames it has published but not yet seen a backend ACK for.
2. The bridge publishes an application-level ACK on
   `tv/dev/{source_id}/ack` **only after** the backend returns 202.
3. Any frame unacked for more than `TV_ACK_TIMEOUT_MS` is retried by
   the sketch over HTTP (which is synchronous and returns the receipt
   status directly). A silent bridge or broker outage therefore
   cannot swallow evidence - the frame gets a second, synchronous
   path.

The bridge itself owns a **SQLite spool** (TV5-07): every accepted
frame is persisted before backend delivery, a worker thread drains it
with bounded exponential backoff, transient failures retry, and
exhausted or terminal failures move to a `dead_letter` table. The
spool survives bridge restart.

## Device-to-backend transport

The reference sketch supports **both** transports and picks one at
boot from `config.h`:

- `TV_TRANSPORT_HTTP` (default) posts directly to
  `POST /api/v1/live/telemetry` over HTTPS with a pinned lab CA.
  Simplest path, no broker required.
- `TV_TRANSPORT_MQTT` publishes to the bridge. HTTP is used as a
  synchronous failover for anything the bridge does not ACK within
  `TV_ACK_TIMEOUT_MS`.

The backend is intentionally **transport-neutral**: the MQTT bridge
validates that the payload `source_id` matches the topic `source_id`
(TV5-03) before signing the outbound POST with the correct token, so
authentication, receipts, evidence sealing, sequencing checks,
malformed logging, and audit history all run in exactly one place.

## Device registration and identification

1. Operator creates the case (`POST /api/v1/cases`) and a live session
   (`POST /api/v1/cases/{case_id}/live-sessions`) listing the physical
   `source_id`.
2. Operator issues a token and edits `backend/.env` so
   `LIVE_SOURCE_TOKENS` is a JSON object mapping each source_id to
   its token (TV5-13). Shell quoting varies:

   ```
   # POSIX shells (bash, zsh):
   LIVE_SOURCE_TOKENS='{"esp32-lab-01":"<hex>"}'

   # cmd.exe:
   set LIVE_SOURCE_TOKENS={"esp32-lab-01":"<hex>"}

   # PowerShell:
   $env:LIVE_SOURCE_TOKENS = '{"esp32-lab-01":"<hex>"}'
   ```

3. Restart FastAPI. Restart the bridge if it is running - it reads
   the same env var.
4. Flash `config.h` onto the ESP32 with `TV_SOURCE_TOKEN` set to the
   same token, `TV_CASE_ID` set to the case id, and (for MQTT) the
   three PEM blocks populated.
5. On boot the ESP32 emits one `heartbeat`; the backend creates the
   device row via the existing collector; the browser live view marks
   the source `online`.

## Connection and heartbeat status

- ESP32 sends `heartbeat` on boot and every 15 s idle. Any successful
  publish resets the timer (TV5-15), so a chatty node does not also
  emit heartbeats.
- The backend's `stale_after_seconds` (default 30 s on the live
  session) marks a source stale when no event has been received. Two
  missed heartbeats therefore transition a source to `stale` in the
  browser.
- The MQTT bridge translates broker LWT `offline` messages into a
  `heartbeat` with `metrics={"link":"offline"}` so the analysis view
  reflects broker-level disconnects immediately rather than waiting
  for the stale timer.

## Evidence storage

Accepted live frames are persisted through the existing
`LiveTelemetryAcceptanceService`: each frame becomes a durable
receipt with `ingested_at` set by the backend clock (never the
device), a canonical event whose `provenance.origin = "live"` carries
source name, source id, adapter version, and normalization version,
and an entry in `audit_events` for the case. Rejected frames are
recorded in `live_ingest_issues` with the raw body (truncated to 64
KiB) when the source token is valid.

Frames with an **invalid** token are rejected before
`record_malformed()` runs, so they leave only an HTTP 401 in the
uvicorn access log (TV5-12). This is intentional at the current
backend to keep unauthenticated attacker input out of the audit
table; an authenticated-failure audit signal, if wanted, is a
separate backend change.

## Forwarding into the common analysis pipeline

No new code path: the canonical event produced from live telemetry
enters `AnalysisService` exactly like batch evidence. Detection rules
(Step 6), correlation, risk scoring, timelines, graphs, and chart
aggregates run unchanged. `AUTH-001` fires from ten `authentication`
failures in the deterministic rule window whether they originate from
`simulate_live.py` or the physical node.

## Controlled suspicious-event scenarios for demonstration

Scenarios live under `hardware/scenarios/` and are reproducible bench
procedures. Each one exists as a shell script and a short operator
note; expected outcomes match the actual backend behavior after the
PR #8 review.

1. **Replay** - `replay.sh`: capture one signed frame, republish it.
   Backend returns the ORIGINAL receipt with `duplicate=true`; no
   new event is created (TV5-11).
2. **Tamper** - `tamper.sh`: modify a metric before republishing.
   Backend records the frame in `live_ingest_issues` as
   `malformed_live_telemetry`.
3. **Rogue device** - `rogue.sh`: publish under an unregistered
   token. HTTP 401; no audit row today (TV5-12).
4. **Environmental anomaly** - `environment.sh`: warm the DHT22
   above `TV_TEMP_C_ALERT_ABOVE`. Requires a Step 6 detection rule;
   see the rule dependency note in `docs/step-5-testing.md`.
5. **Unauthorized actuation** - `actuation.sh`: flip the relay via
   the ISOLATED manual override on the relay module (TV5-01). Node
   emits `device_state` for the relay without a preceding `command`
   event; correlator flags the ungrounded state change.
6. **Reconnect** - `reconnect.sh`: pull the Wi-Fi antenna for 20 s.
   LWT fires, broker publishes `offline`, bridge emits a `heartbeat`
   with `link=offline`. On reconnect the browser SSE view resumes
   with `Last-Event-ID`.

## Verify end-to-end live ingestion

See `docs/step-5-testing.md` for the full three-ladder acceptance
procedure and the merge-gate checklist.

The hardware kit is under `hardware/`:

- `hardware/esp32/traceveil_node/traceveil_node.ino` - reference sketch.
- `hardware/esp32/traceveil_node/config.h.example` - per-node config.
- `hardware/mqtt_bridge/bridge.py` - MQTT-to-HTTP bridge with spool.
- `hardware/mqtt_bridge/mosquitto.conf` - broker config.
- `hardware/mqtt_bridge/traceveil.acl` - per-CN topic ACL (TV5-03).
- `hardware/mqtt_bridge/requirements.txt` - bridge dependencies.
- `hardware/scenarios/*` - reproducible suspicious-event scripts.
