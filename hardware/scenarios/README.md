# Step 5 controlled suspicious-event scenarios

Each script is a reproducible bench procedure. They assume the ESP32 node is
powered, the MQTT bridge is running, FastAPI is up, and `TV_SOURCE_ID`,
`TV_SOURCE_TOKEN`, `TV_CASE_ID`, and `TV_API_BASE` are exported. All
scripts leave the case in an investigable state - stopping the live session
afterwards produces the same historical view as any batch case.

| Script | Scenario | Expected backend result |
| --- | --- | --- |
| `replay.sh`    | Capture one signed frame and republish it. | Frame accepted, receipt flags `sequence_regression`. |
| `tamper.sh`    | Modify a metric before republishing. | Rejected as `malformed_live_telemetry`; row in `live_ingest_issues`. |
| `rogue.sh`     | Publish under an unregistered source. | Rejected as `invalid_live_source_token`; audit row only, no evidence. |
| `environment.sh` | Warm the DHT22 above `TV_TEMP_C_ALERT_ABOVE`. | Environment detection rule fires; alert linked to underlying evidence ids. |
| `actuation.sh` | Trigger the relay pin bypassing the command path. | `device_state` without a preceding `command`; correlator flags ungrounded state change. |
| `reconnect.sh` | Pull the antenna for 20 s. | LWT `offline` -> bridge emits `heartbeat` with `link=lost`; SSE client reconnects with `Last-Event-ID`. |

Every scenario should be followed by:

```
python backend/simulate_live.py --scenario heartbeat --count 1 \
  --source-id "$TV_SOURCE_ID" --token "$TV_SOURCE_TOKEN" --case-id "$TV_CASE_ID"
```

...to re-mark the source as online and leave the environment in a
predictable state for the next operator.
