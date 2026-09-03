"""Traceveil Step 5 MQTT-to-HTTP bridge.

Subscribes to ``tv/dev/+/telemetry`` on a mosquitto broker and forwards each
frame to the existing authenticated HTTP collector at
``POST /api/v1/live/telemetry`` with the correct ``X-Traceveil-Source-Token``.

The bridge is deliberately dumb: it does not normalize, sign, or reshape
telemetry. Validation, sequence checks, malformed logging, receipts, and
audit history all remain in the backend so both transports produce identical
evidence. The only extra behavior is translating broker LWT ``status``
messages into ``heartbeat`` events so link loss becomes visible in the
analysis view without waiting for the stale-source timer.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sys
from datetime import datetime, timezone
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError

import paho.mqtt.client as mqtt


LOG = logging.getLogger("traceveil.bridge")


def load_source_tokens(raw: str) -> dict[str, str]:
    """Parses ``LIVE_SOURCE_TOKENS`` in the exact JSON shape the backend expects.

    Example: ``{"esp32-lab-01": "long-random-token"}``. The bridge reads the
    same env var the backend reads so operator setup is a single edit.
    """
    if not raw.strip():
        raise SystemExit("no source tokens provided; set LIVE_SOURCE_TOKENS")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"LIVE_SOURCE_TOKENS must be JSON: {exc}") from exc
    if not isinstance(parsed, dict) or not parsed:
        raise SystemExit("LIVE_SOURCE_TOKENS must be a non-empty JSON object")
    tokens: dict[str, str] = {}
    for source_id, token in parsed.items():
        if not isinstance(source_id, str) or not isinstance(token, str) or not source_id or not token:
            raise SystemExit(f"invalid LIVE_SOURCE_TOKENS entry: {source_id!r}")
        tokens[source_id] = token
    return tokens


def parse_source_from_topic(topic: str) -> str | None:
    parts = topic.split("/")
    # tv/dev/{source_id}/telemetry  or  tv/dev/{source_id}/status
    if len(parts) == 4 and parts[0] == "tv" and parts[1] == "dev":
        return parts[2]
    return None


def now_iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


class Bridge:
    def __init__(self, api_base: str, tokens: dict[str, str], case_id_default: int) -> None:
        self.api_base = api_base.rstrip("/")
        self.tokens = tokens
        self.case_id_default = case_id_default

    # -- HTTP forwarding ---------------------------------------------------
    def post(self, source_id: str, body: dict) -> None:
        token = self.tokens.get(source_id)
        if token is None:
            LOG.warning("dropping frame from unregistered source %s", source_id)
            return
        data = json.dumps(body).encode("utf-8")
        req = urlrequest.Request(
            f"{self.api_base}/live/telemetry",
            data=data,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-Traceveil-Source-Token": token,
                "Accept": "application/json",
            },
        )
        try:
            with urlrequest.urlopen(req, timeout=5) as response:
                LOG.info(
                    "forwarded source=%s seq=%s status=%d",
                    source_id,
                    body.get("sequence"),
                    response.status,
                )
        except HTTPError as exc:
            # Malformed payloads are recorded by the backend; log and move on.
            LOG.warning(
                "backend rejected source=%s status=%d body=%s",
                source_id,
                exc.code,
                exc.read().decode("utf-8", errors="replace")[:400],
            )
        except URLError as exc:
            LOG.error("backend unreachable for source=%s: %s", source_id, exc)

    # -- MQTT callbacks ----------------------------------------------------
    def on_connect(self, client: mqtt.Client, _userdata, _flags, rc: int) -> None:
        if rc != 0:
            LOG.error("mqtt connect failed rc=%d", rc)
            return
        LOG.info("mqtt connected; subscribing to tv/dev/+/telemetry and .../status")
        client.subscribe([("tv/dev/+/telemetry", 1), ("tv/dev/+/status", 1)])

    def on_message(self, _client: mqtt.Client, _userdata, msg: mqtt.MQTTMessage) -> None:
        source_id = parse_source_from_topic(msg.topic)
        if source_id is None:
            LOG.debug("ignoring topic %s", msg.topic)
            return

        payload_raw = msg.payload.decode("utf-8", errors="replace")
        # Status transitions (LWT) become heartbeat events so link loss lands
        # in the same evidence and audit trail as any other frame.
        if msg.topic.endswith("/status"):
            try:
                status = json.loads(payload_raw).get("status", "unknown")
            except json.JSONDecodeError:
                status = payload_raw.strip() or "unknown"
            self.post(
                source_id,
                {
                    "schema_version": "1.0",
                    "case_id": self.case_id_default,
                    "source_id": source_id,
                    "device_id": source_id,
                    "event_type": "heartbeat",
                    "observed_at": now_iso_utc(),
                    "metrics": {"link": status},
                },
            )
            return

        try:
            body = json.loads(payload_raw)
        except json.JSONDecodeError:
            LOG.warning("dropping non-JSON payload from %s", source_id)
            return
        if not isinstance(body, dict):
            LOG.warning("dropping non-object payload from %s", source_id)
            return
        # Do NOT rewrite the body. The backend is the sole authority on
        # validation, sequencing, and evidence sealing.
        self.post(source_id, body)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--broker-host", default=os.getenv("TV_MQTT_HOST", "127.0.0.1"))
    parser.add_argument("--broker-port", type=int, default=int(os.getenv("TV_MQTT_PORT", "8883")))
    parser.add_argument("--broker-tls", action="store_true", default=os.getenv("TV_MQTT_TLS", "1") == "1")
    parser.add_argument("--api-base", default=os.getenv("TV_API_BASE", "http://127.0.0.1:8000/api/v1"))
    parser.add_argument("--case-id", type=int, default=int(os.getenv("TV_DEFAULT_CASE_ID", "1")))
    parser.add_argument("--log-level", default=os.getenv("TV_LOG_LEVEL", "INFO"))
    args = parser.parse_args()

    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    tokens_raw = os.getenv("LIVE_SOURCE_TOKENS", "")
    tokens = load_source_tokens(tokens_raw)
    LOG.info("loaded %d source tokens", len(tokens))

    bridge = Bridge(api_base=args.api_base, tokens=tokens, case_id_default=args.case_id)
    client = mqtt.Client(client_id="traceveil-bridge", clean_session=True)
    if args.broker_tls:
        client.tls_set()  # supply lab CA/cert via env if the broker requires it
    client.on_connect = bridge.on_connect
    client.on_message = bridge.on_message

    def _stop(_signum, _frame):
        LOG.info("stopping bridge")
        client.disconnect()
        sys.exit(0)

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    LOG.info("connecting to broker %s:%d tls=%s", args.broker_host, args.broker_port, args.broker_tls)
    client.connect(args.broker_host, args.broker_port, keepalive=30)
    client.loop_forever()


if __name__ == "__main__":
    main()
