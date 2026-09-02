# Step 5 - Testing

Three ladders. Climb them in order: each one catches a different class of
problem, and the higher rungs assume the lower ones already pass.

## Ladder 1 - Automated (no hardware, no broker)

Runs entirely in the backend virtualenv. This is the fastest signal and
what CI should run.

```bash
cd backend
pip install -e '.[dev]'
pytest tests/test_live_telemetry_contract.py       tests/test_phase3_api.py       tests/test_mqtt_bridge_forwarding.py -q
```

What each file proves:

- `test_live_telemetry_contract.py` - the existing `LiveTelemetryInput`
  contract still accepts the shape the ESP32 sketch emits. Step 5 must not
  regress it.
- `test_phase3_api.py` - the HTTP collector, token auth, receipts, SSE
  replay, and audit trail behave. These are the same primitives Step 5
  relies on.
- `test_mqtt_bridge_forwarding.py` (new in Step 5) - the bridge translates
  an MQTT frame into an HTTP POST against the real FastAPI app in-process,
  produces a device row, translates LWT `status` into a heartbeat, and
  drops frames from unregistered sources. No mosquitto process is needed.

If those pass, the software integration is sound and the remaining tests
are about physical wiring and network.

## Ladder 2 - Bridge + simulator (no hardware)

Runs the real mosquitto broker and the real `bridge.py`, but publishes
frames with `mosquitto_pub` in place of the ESP32. Confirms the broker,
bridge, and backend are correctly wired on the demo host.

Prereqs: `mosquitto` + `mosquitto-clients` installed, and the backend
running with `LIVE_SOURCE_TOKENS='{"live-lab-01":"traceveil-demo-token"}'`.

```bash
# Terminal A - start the broker with the lab config (edit paths first)
mosquitto -c hardware/mqtt_bridge/mosquitto.conf -v

# Terminal B - start the bridge
cd hardware/mqtt_bridge
pip install -r requirements.txt
LIVE_SOURCE_TOKENS='{"live-lab-01":"traceveil-demo-token"}'   TV_API_BASE=http://127.0.0.1:8000/api/v1   TV_MQTT_HOST=127.0.0.1 TV_MQTT_PORT=8883 TV_DEFAULT_CASE_ID=1   python bridge.py

# Terminal C - watch the SSE stream
curl -N -sS "http://127.0.0.1:8000/api/v1/live/stream?case_id=1&topics=events,alerts,heartbeat"

# Terminal D - simulate the ESP32 by publishing directly to MQTT
NOW=$(date -u +%Y-%m-%dT%H:%M:%S.000+00:00)
mosquitto_pub -h 127.0.0.1 -p 8883 --cafile /etc/mosquitto/ca/traceveil-lab-ca.crt   -t tv/dev/live-lab-01/telemetry -q 1 -m "{
    \"schema_version\":\"1.0\",\"case_id\":1,
    \"source_id\":\"live-lab-01\",\"device_id\":\"live-lab-01\",
    \"event_type\":\"telemetry\",\"observed_at\":\"$NOW\",
    \"sequence\":1,\"metrics\":{\"temperature_c\":23.1,\"humidity_pct\":40.0,\"motion\":false}
  }"
```

Expected:

- Bridge logs `forwarded source=live-lab-01 seq=1 status=202`.
- SSE stream (Terminal C) emits an `events` frame with the new device.
- `GET /api/v1/cases/1/live/devices` returns the source with a recent
  `last_seen_at`.

You can also re-run the existing HTTP-path acceptance without any of the
above:

```bash
cd backend
python simulate_live.py --scenario suspicious --count 10   --source-id live-lab-01 --token traceveil-demo-token
```

The suspicious scenario must still create a persisted `AUTH-001` alert -
Step 5 changed nothing on that path and should not have broken it.

## Ladder 3 - Physical ESP32 on the bench

Prereqs from the docs: ESP32-WROOM-32, DHT22 on GPIO 4, HC-SR501 on
GPIO 27, relay on GPIO 26, node powered from the demo laptop USB, lab AP
reachable, backend + broker + bridge running as in Ladder 2.

```bash
# 1. Copy per-node config
cp hardware/esp32/traceveil_node/config.h.example      hardware/esp32/traceveil_node/config.h
$EDITOR hardware/esp32/traceveil_node/config.h        # SSID, PSK, TV_CASE_ID, TV_SOURCE_TOKEN

# 2. Build and flash (arduino-cli shown; the Arduino IDE works identically)
arduino-cli core install esp32:esp32
arduino-cli lib install "DHT sensor library" "Adafruit Unified Sensor"   "ArduinoJson" "PubSubClient"
arduino-cli compile --fqbn esp32:esp32:esp32   hardware/esp32/traceveil_node/traceveil_node.ino
arduino-cli upload  --fqbn esp32:esp32:esp32 -p /dev/ttyUSB0   hardware/esp32/traceveil_node/traceveil_node.ino

# 3. Watch the node
arduino-cli monitor -p /dev/ttyUSB0 -c baudrate=115200
```

Acceptance walk (matches the roadmap Step 5 "Verify end-to-end live
ingestion" line):

1. Within 3 s of boot, `GET /api/v1/cases/<id>/live/devices` shows the
   source as `online` and a heartbeat receipt exists.
2. Telemetry frames arrive at the configured 3 s cadence; the browser
   live view at `http://localhost:5173/live?case=<id>` updates without
   refresh.
3. Run each script under `hardware/scenarios/` in turn. Confirm:
   - `replay.sh` produces a receipt flagged for sequence regression.
   - `tamper.sh` produces a row in `live_ingest_issues`.
   - `rogue.sh` produces HTTP 403 and an audit row, no evidence.
   - `environment.sh` triggers the environment detection rule with
     linked evidence ids (see the note below if the rule is missing).
   - `actuation.sh` produces a `device_state` without a preceding
     `command`; correlator flags it.
   - `reconnect.sh` shows `link=lost` then a clean resume from
     `Last-Event-ID`.
4. Stop the live session in the browser, power the ESP32 down, and open
   the case tabs (events, alerts, timeline, graph, analytics, report,
   audit). Every scenario must still be investigable from persistence
   alone - this is the roadmap Step 12 pre-check.

## Rule dependency note

The environment and actuation scenarios rely on Step 6 detection rules
that fire on `metrics.threshold_over_temp = true` and on a `device_state`
frame whose `metrics.relay` transitions without a preceding `command`
event in the case timeline. If your `AnalysisService` does not ship those
rules yet, either add them to `backend/app/analysis/detection.py` or
retarget the two scenarios at rules that do exist (the `AUTH-001` path
that `simulate_live.py --scenario suspicious` exercises is definitely
present).

## When something fails

- **`403 invalid_live_source_token`** - the source_id in the frame is not
  a key in the backend's `LIVE_SOURCE_TOKENS`, or the token does not
  match. Fix `backend/.env`, restart FastAPI, and (for the bridge) restart
  it too so it re-reads the env var.
- **`422 malformed_live_telemetry`** - the frame violates the canonical
  contract. Common causes: missing timezone on `observed_at`, a metric
  name with a space, a non-finite float, unknown top-level field.
- **Bridge silent, broker silent** - check `mosquitto -v` output. In lab
  configs the most common cause is a client cert whose CN does not match
  `TV_SOURCE_ID` (the broker enforces `use_identity_as_username`).
- **ESP32 refuses to publish** - if the serial monitor shows `ntp failed`,
  NTP is unreachable from the lab VLAN. Either open UDP 123 outbound to
  `pool.ntp.org` or point `configTime` at a local NTP server.
