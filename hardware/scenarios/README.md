# Step 5 controlled suspicious-event scenarios

Each script is a reproducible bench procedure. They assume the ESP32
node is powered, the MQTT bridge is running, FastAPI is up, and the
required environment (`TV_SOURCE_ID`, `TV_CASE_ID`, `TV_API_BASE`, and
for MQTT scripts the CA/cert/key file paths) is exported. All scripts
leave the case in an investigable state - stopping the live session
afterwards produces the same historical view as any batch case.

| Script | Scenario | Expected backend result |
| --- | --- | --- |
| `replay.sh`    | Capture one signed frame and republish it. | Bridge forwards; backend returns ORIGINAL receipt with `duplicate=true`; no new event; a `live.replay_detected` row is added to audit_events (TV5-11). |
| `tamper.sh`    | Modify a metric before republishing. | Rejected as `malformed_live_telemetry`; row in `live_ingest_issues`. |
| `rogue.sh`     | POST with an unregistered token. | HTTP 401; one bounded `live.auth_failure` row in audit_events, rate-limited per (source_id / client_ip) (TV5-12). |
| `environment.sh` | Warm the DHT22 above `TV_TEMP_C_ALERT_ABOVE`. | Environment detection rule fires; alert linked to underlying evidence ids. (Rule dependency: see docs/step-5-live-iot.md.) |
| `actuation.sh` | SAFE: flip the relay via the isolated manual override, not by tapping GPIO (TV5-01, TV5-06). | `device_state` without a preceding `command`; correlator flags ungrounded state change. |
| `reconnect.sh` | Pull the antenna for 20 s. | LWT `offline` -> bridge emits `heartbeat` with `link=lost`; SSE client reconnects with `Last-Event-ID`. |

After running a scenario, re-mark the source online with:

```
python backend/simulate_live.py --scenario heartbeat --count 1 \
  --source-id "$TV_SOURCE_ID" --token "$TV_SOURCE_TOKEN" --case-id "$TV_CASE_ID"
```
