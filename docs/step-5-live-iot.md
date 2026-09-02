# Step 5 - Live IoT Integration

Phase 3 completed the software-only live path: `POST /api/v1/live/telemetry`
authenticates with `X-Traceveil-Source-Token`, validates `LiveTelemetryInput`,
issues a durable receipt, normalizes into a canonical event, and forwards to
the deterministic analysis pipeline that Step 6 owns. Step 5 adds the
**physical device** and an **optional MQTT transport** without changing that
contract; the simulator (`backend/simulate_live.py`) remains the acceptance
surrogate and the hardware node must behave identically on the wire.

## Hardware selection

| Item | Choice | Why |
| --- | --- | --- |
| Microcontroller | ESP32-WROOM-32 dev kit | Onboard Wi-Fi + TLS, dual core, mature Arduino core, HMAC/SHA in mbedTLS. |
| Environment sensor | DHT22 (AM2302) on GPIO 4 | One-wire temperature and humidity; feeds `telemetry` metrics. |
| Motion sensor | HC-SR501 PIR on GPIO 27 | Digital `device_state` transitions; drives the unexpected-motion scenario. |
| Actuator | Single-channel 5 V relay on GPIO 26 | Emits `command` and `device_state` events; drives the unauthorized-actuation scenario. |
| Status LED | Onboard GPIO 2 | Solid = Wi-Fi up, blink = ingest error, off = offline. |
| Power | 5 V USB from the demo laptop | Keeps the node on the same isolated bench as the AP. |

Every physical node maps to exactly one Traceveil `source_id` and one
`device_id`. Additional sensors extend `metrics` in place; they do **not**
create additional canonical devices without a matching profile in Step 3.

## Controlled laboratory topology

```
[ESP32 sensor node] ---Wi-Fi (WPA2)--- [Lab AP / isolated VLAN]
                                            |
                          (no route to the public internet)
                                            |
              +-----------------------------+-----------------------------+
              |                                                           |
              v                                                           v
   [ mosquitto broker :8883 ]                              [ FastAPI :8000 /api/v1 ]
   tv/dev/{source_id}/telemetry                             live/telemetry (X-Traceveil-Source-Token)
   tv/dev/{source_id}/status  (retained LWT)                cases/{case_id}/live-sessions
              |                                                           ^
              v                                                           |
   [ hardware/mqtt_bridge/bridge.py ] ---HTTPS---> POSTs each frame ------+
```

Rules for the lab environment:

- The AP is on its own VLAN with no default route. Only the broker host and
  the FastAPI host are reachable from the ESP32 subnet.
- The Traceveil source token is provisioned via `LIVE_SOURCE_TOKENS` in
  `backend/.env` (one token per `source_id`) and flashed onto the ESP32 via
  `config.h`. Tokens never appear in git history.
- The broker uses `mosquitto` with client-certificate auth on port 8883.
  Every node has its own client cert; anonymous access is disabled.
- Time is synchronized with `pool.ntp.org` on both the ESP32 and the FastAPI
  host. Devices without NTP must not ingest - `observed_at` requires an
  accurate timezone-aware timestamp per the canonical event contract.

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

- `event_type` is one of `telemetry | device_state | authentication | network
  | command | heartbeat`. Motion transitions send `device_state`; relay
  toggles send `command`; a periodic keepalive sends `heartbeat` with an
  empty `metrics` object.
- `sequence` is strictly monotonic per (`source_id`, boot). It is stored in
  ESP32 NVS so it survives a reset. A regression is a signal for the
  replay-detection scenario.
- `observed_at` is set from the local NTP-synced clock in UTC. If NTP has
  never synced, the node refuses to publish.
- `metrics` keys match `^[A-Za-z0-9._:-]+$` and values are finite scalars
  (bool, int, float, string, null). No nested structures - the collector
  rejects them.

MQTT topics (only when the MQTT bridge is used):

- `tv/dev/{source_id}/telemetry` - device -> bridge, QoS 1, not retained.
- `tv/dev/{source_id}/status` - retained LWT payload `{"status":"offline"}`
  set on connect; the node publishes `{"status":"online"}` immediately after
  a successful subscribe. The bridge maps LWT changes to `heartbeat` events
  so device liveness enters the same evidence trail.

## Device-to-backend transport

The reference sketch supports **both** transports and picks one at boot from
`config.h`:

- `TV_TRANSPORT_HTTP` (default) posts directly to
  `POST /api/v1/live/telemetry` over HTTPS. Simplest path, no broker.
- `TV_TRANSPORT_MQTT` publishes to the bridge; if the broker is unreachable
  for `TV_MQTT_FAILOVER_MS`, the sketch falls back to HTTP for that frame so
  ingestion never silently stalls.

The backend is intentionally **transport-neutral**: the MQTT bridge validates
and re-signs each frame with the source token before POSTing to the same
`/api/v1/live/telemetry` endpoint, so authentication, receipts, evidence
sealing, sequencing checks, malformed logging, and audit history all run in
exactly one place.

## Device registration and identification

1. Operator creates the case (`POST /api/v1/cases`) and a live session
   (`POST /api/v1/cases/{case_id}/live-sessions`) listing the physical
   `source_id`.
2. Operator issues a token and adds `LIVE_SOURCE_TOKENS="esp32-lab-01=<hex>"`
   to `backend/.env`, then restarts FastAPI.
3. Operator flashes `config.h` onto the ESP32 with `TV_SOURCE_TOKEN` set to
   that same hex string, and `TV_CASE_ID` set to the case id.
4. On boot the ESP32 emits one `heartbeat` event; the backend accepts it,
   creates the device row via the existing collector, and the browser view
   marks the source `online`.

There is no separate hardware registration table - reusing
`LIVE_SOURCE_TOKENS` keeps every access-control decision in one file the
operator already audits.

## Connection and heartbeat status

- ESP32 sends `heartbeat` every 15 s while idle. Any telemetry publish
  resets the timer, so a chatty node does not spam heartbeats.
- The backend's existing `stale_after_seconds` (default 30 s on the live
  session) marks a source stale when no event has been received. Two missed
  heartbeats therefore transition a source to `stale` in the browser.
- The MQTT bridge additionally translates broker LWT `offline` messages
  into a `heartbeat` with `metrics={"link":"lost"}` so the analysis view
  reflects broker-level disconnects even before the stale timer fires.

## Evidence storage

Accepted live frames are persisted through the existing
`LiveTelemetryAcceptanceService`: each frame becomes a durable receipt with
`ingested_at` set by the backend clock (never the device), a canonical
event whose `provenance.origin = "live"` and `provenance.source_type = "live"`
carries source name, source id, adapter version, and normalization version,
and an entry in `audit_events` for the case. Rejected frames are recorded
in `live_ingest_issues` with the raw body (truncated to 64 KiB) so a
malformed hardware scenario is auditable end-to-end.

## Forwarding into the common analysis pipeline

No new code path: the canonical event produced from live telemetry enters
`AnalysisService` exactly like batch evidence. Detection rules (Step 6),
correlation, risk scoring, timelines, graphs, and chart aggregates run
unchanged. `AUTH-001` fires from ten `authentication` failures in the
deterministic rule window whether they originate from `simulate_live.py` or
the physical node.

## Controlled suspicious-event scenarios for demonstration

Scenarios live under `hardware/scenarios/` and are reproducible bench
procedures. Each one exists as a shell/PowerShell script and a short
operator note.

1. **Replay** - `replay.sh`: capture one signed frame with
   `mosquitto_sub -t 'tv/dev/+/telemetry' -F '%p' | tee capture.json`,
   republish it with `mosquitto_pub`. Bridge accepts and forwards; backend
   flags `sequence` regression on the receipt.
2. **Tamper** - `tamper.sh`: modify one metric before republishing.
   Backend records the frame in `live_ingest_issues` as
   `malformed_live_telemetry` because the canonical shape or sequence check
   fails; audit trail shows the tamper.
3. **Rogue device** - `rogue.sh`: publish under an unregistered
   `source_id`. `verify_source` fails with `invalid_live_source_token`;
   the frame never becomes evidence, but the rejection is audited.
4. **Environmental anomaly** - `environment.sh`: warm the DHT22 above the
   configured threshold with a hair dryer. Node emits normal `telemetry`
   frames; the environment detection rule surfaces the anomaly with the
   underlying evidence ids.
5. **Unauthorized actuation** - `actuation.sh`: physically bridge the
   relay control pin. Node emits `device_state` for the relay without a
   preceding `command` event; correlator flags the ungrounded state change.
6. **Reconnect** - `reconnect.sh`: pull the Wi-Fi antenna for 20 s. LWT
   fires, broker publishes `offline` on `tv/dev/{source_id}/status`, bridge
   emits a `heartbeat` with `link=lost`. On reconnect the browser SSE view
   resumes with `Last-Event-ID` and no gap is lost.

## Verify end-to-end live ingestion

Manual acceptance for a demonstration run:

1. `pytest backend/tests/test_live_telemetry_contract.py -q` still passes
   (Step 3 contract is unchanged).
2. Start FastAPI, Vite, and the MQTT bridge; power the ESP32.
3. Watch `mosquitto_sub -v -t 'tv/#'` and `journalctl -u traceveil-api -f`
   simultaneously. Every publish becomes exactly one POST and exactly one
   receipt.
4. Open `http://localhost:5173/live?case=<id>`; confirm the device chip
   shows online within 3 s, telemetry cards update, and the SSE stream
   reconnects with `Last-Event-ID` after `reconnect.sh`.
5. Run `replay.sh`, `tamper.sh`, `rogue.sh`, `environment.sh`, and
   `actuation.sh`; confirm receipts, `live_ingest_issues`, alerts,
   incidents, timeline, graph, and audit tabs all reflect the scenario.
6. Stop the live session from the browser, then open the case tabs and
   verify that the captured incident is fully investigable **after** the
   physical device is powered down. This is the roadmap's Step 12
   pre-check.

The hardware kit is under `hardware/`:

- `hardware/esp32/traceveil_node/traceveil_node.ino` - reference sketch.
- `hardware/esp32/traceveil_node/config.h.example` - per-node config.
- `hardware/mqtt_bridge/bridge.py` - MQTT-to-HTTP bridge that speaks the
  existing `/api/v1/live/telemetry` contract.
- `hardware/mqtt_bridge/mosquitto.conf` - broker config for the lab VLAN.
- `hardware/mqtt_bridge/requirements.txt` - bridge dependencies.
- `hardware/scenarios/*` - reproducible suspicious-event scripts.
