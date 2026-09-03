"""Traceveil Step 5 MQTT-to-HTTP bridge.

Subscribes to ``tv/dev/+/telemetry`` and ``tv/dev/+/status`` on a mosquitto
broker and forwards each frame to the existing authenticated HTTP collector
at ``POST /api/v1/live/telemetry`` with the correct
``X-Traceveil-Source-Token``.

Review-driven behavior (TV5-02, TV5-03, TV5-07, TV5-09):

* Mutual TLS is required when the bridge is configured to use MQTT+TLS.
  Startup refuses if ``TV_MQTT_CA_FILE``, ``TV_MQTT_CLIENT_CERT``, and
  ``TV_MQTT_CLIENT_KEY`` are not present. ``tls_set`` without material is
  never called.
* Every frame's payload ``source_id`` must match the topic ``source_id``.
  A mismatch is a topic-ACL bypass attempt and is dropped with an error
  log, not forwarded.
* Every accepted frame is persisted to a small on-disk SQLite spool
  before backend delivery. A worker thread drains the spool with
  bounded exponential backoff. HTTP 4xx (except 429) marks the frame as
  a terminal failure in ``dead_letter``; 2xx marks it delivered; 5xx,
  429, and network errors retry. The spool survives bridge restart, so
  a backend outage never permanently drops evidence.
* After the backend accepts a frame, the bridge publishes an
  application-level acknowledgement on ``tv/dev/{source_id}/ack`` with
  the frame's ``sequence``. The ESP32 sketch uses these ACKs to drop
  frames from its retry buffer, giving end-to-end delivery guarantees
  even though the MQTT hop itself is QoS 0.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import queue
import signal
import sqlite3
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError

try:  # pragma: no cover - exercised in production, stubbed in unit tests
    import paho.mqtt.client as mqtt
except ImportError:  # pragma: no cover
    mqtt = None  # type: ignore[assignment]


LOG = logging.getLogger("traceveil.bridge")


# ---------------------------------------------------------------------------
# Configuration parsing
# ---------------------------------------------------------------------------
def load_source_tokens(raw: str) -> dict[str, str]:
    """Parses ``LIVE_SOURCE_TOKENS`` in the exact JSON shape the backend expects.

    Example: ``{"esp32-lab-01": "long-random-token"}``. Same env var, same
    format the backend reads, so operator setup is a single edit.
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


# ---------------------------------------------------------------------------
# Durable spool (TV5-07)
# ---------------------------------------------------------------------------
_INIT_SQL = """
CREATE TABLE IF NOT EXISTS spool (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    received_at   TEXT    NOT NULL,
    source_id     TEXT    NOT NULL,
    sequence      INTEGER,
    body_json     TEXT    NOT NULL,
    attempts      INTEGER NOT NULL DEFAULT 0,
    next_attempt  REAL    NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_spool_next_attempt ON spool(next_attempt);

CREATE TABLE IF NOT EXISTS dead_letter (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    original_id   INTEGER NOT NULL,
    failed_at     TEXT    NOT NULL,
    source_id     TEXT    NOT NULL,
    sequence      INTEGER,
    body_json     TEXT    NOT NULL,
    reason        TEXT    NOT NULL
);
"""


class Spool:
    """Persistent bounded queue of frames to forward to the backend."""

    def __init__(self, path: Path, max_attempts: int = 8, max_size: int = 10_000) -> None:
        self.path = path
        self.max_attempts = max_attempts
        self.max_size = max_size
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self._conn.executescript(_INIT_SQL)

    def enqueue(self, source_id: str, body: dict) -> int | None:
        with self._lock:
            depth = self._conn.execute("SELECT COUNT(*) FROM spool").fetchone()[0]
            if depth >= self.max_size:
                LOG.error("spool full (%d rows); dropping frame from %s", depth, source_id)
                return None
            cur = self._conn.execute(
                "INSERT INTO spool(received_at, source_id, sequence, body_json, attempts, next_attempt)"
                " VALUES(?,?,?,?,0,0)",
                (now_iso_utc(), source_id, body.get("sequence"), json.dumps(body)),
            )
            return int(cur.lastrowid)

    def next_ready(self, now: float | None = None) -> tuple[int, str, int | None, dict] | None:
        now = time.time() if now is None else now
        with self._lock:
            row = self._conn.execute(
                "SELECT id, source_id, sequence, body_json FROM spool"
                " WHERE next_attempt <= ? ORDER BY id LIMIT 1",
                (now,),
            ).fetchone()
        if row is None:
            return None
        return int(row[0]), str(row[1]), (int(row[2]) if row[2] is not None else None), json.loads(row[3])

    def mark_delivered(self, row_id: int) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM spool WHERE id=?", (row_id,))

    def defer(self, row_id: int, delay_s: float) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE spool SET attempts = attempts + 1, next_attempt = ? WHERE id=?",
                (time.time() + delay_s, row_id),
            )

    def attempts(self, row_id: int) -> int:
        with self._lock:
            row = self._conn.execute("SELECT attempts FROM spool WHERE id=?", (row_id,)).fetchone()
        return int(row[0]) if row else 0

    def dead_letter(self, row_id: int, reason: str) -> None:
        with self._lock:
            row = self._conn.execute(
                "SELECT source_id, sequence, body_json FROM spool WHERE id=?", (row_id,)
            ).fetchone()
            if row is None:
                return
            self._conn.execute(
                "INSERT INTO dead_letter(original_id, failed_at, source_id, sequence, body_json, reason)"
                " VALUES(?,?,?,?,?,?)",
                (row_id, now_iso_utc(), row[0], row[1], row[2], reason[:400]),
            )
            self._conn.execute("DELETE FROM spool WHERE id=?", (row_id,))

    def depth(self) -> tuple[int, int]:
        with self._lock:
            spool_depth = self._conn.execute("SELECT COUNT(*) FROM spool").fetchone()[0]
            dead_depth = self._conn.execute("SELECT COUNT(*) FROM dead_letter").fetchone()[0]
        return int(spool_depth), int(dead_depth)

    def close(self) -> None:
        with self._lock:
            self._conn.close()


# ---------------------------------------------------------------------------
# Bridge
# ---------------------------------------------------------------------------
_TRANSIENT_STATUS = {429, 500, 502, 503, 504}


class Bridge:
    """Forwards MQTT frames to the backend with a durable retry queue."""

    def __init__(
        self,
        api_base: str,
        tokens: dict[str, str],
        case_id_default: int,
        spool: Spool,
        mqtt_client=None,
        request_timeout_s: float = 5.0,
    ) -> None:
        self.api_base = api_base.rstrip("/")
        self.tokens = tokens
        self.case_id_default = case_id_default
        self.spool = spool
        self.mqtt_client = mqtt_client
        self.request_timeout_s = request_timeout_s
        self._stop = threading.Event()

    # -- HTTP forwarding ---------------------------------------------------
    def _post(self, source_id: str, body: dict) -> tuple[int, str]:
        """Returns (status_code, reason). Raises URLError on network failure."""
        token = self.tokens[source_id]
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
            with urlrequest.urlopen(req, timeout=self.request_timeout_s) as response:
                return int(response.status), "ok"
        except HTTPError as exc:
            reason = exc.read().decode("utf-8", errors="replace")[:400]
            return int(exc.code), reason

    def _publish_ack(self, source_id: str, sequence: int | None) -> None:
        if self.mqtt_client is None or sequence is None:
            return
        topic = f"tv/dev/{source_id}/ack"
        try:
            self.mqtt_client.publish(topic, json.dumps({"sequence": sequence}), qos=1, retain=False)
        except Exception as exc:  # pragma: no cover - defensive
            LOG.warning("failed to publish ack on %s: %s", topic, exc)

    # -- Spool worker (TV5-07) ---------------------------------------------
    def process_once(self) -> bool:
        """Attempts one spooled frame. Returns True if one was processed."""
        item = self.spool.next_ready()
        if item is None:
            return False
        row_id, source_id, sequence, body = item

        if source_id not in self.tokens:
            self.spool.dead_letter(row_id, "unregistered_source")
            LOG.warning("dead-lettered frame from unregistered source %s", source_id)
            return True

        try:
            status, reason = self._post(source_id, body)
        except URLError as exc:
            attempts = self.spool.attempts(row_id) + 1
            if attempts >= self.spool.max_attempts:
                self.spool.dead_letter(row_id, f"network_exhausted:{exc}")
                LOG.error("dead-lettered source=%s seq=%s after %d attempts: %s",
                          source_id, sequence, attempts, exc)
            else:
                delay = min(60.0, 2 ** attempts)
                self.spool.defer(row_id, delay)
                LOG.warning("network error source=%s seq=%s attempt=%d; retry in %.1fs (%s)",
                            source_id, sequence, attempts, delay, exc)
            return True

        if 200 <= status < 300:
            self.spool.mark_delivered(row_id)
            self._publish_ack(source_id, sequence)
            LOG.info("forwarded source=%s seq=%s status=%d", source_id, sequence, status)
            return True

        if status in _TRANSIENT_STATUS:
            attempts = self.spool.attempts(row_id) + 1
            if attempts >= self.spool.max_attempts:
                self.spool.dead_letter(row_id, f"transient_exhausted:{status}:{reason}")
                LOG.error("dead-lettered source=%s seq=%s after %d transient failures",
                          source_id, sequence, attempts)
            else:
                delay = min(60.0, 2 ** attempts)
                self.spool.defer(row_id, delay)
                LOG.warning("transient %d source=%s seq=%s attempt=%d; retry in %.1fs",
                            status, source_id, sequence, attempts, delay)
            return True

        # Terminal 4xx. The backend will have recorded the frame in
        # live_ingest_issues (for malformed) or refused it (bad token);
        # either way retrying is not going to help.
        self.spool.dead_letter(row_id, f"terminal:{status}:{reason}")
        LOG.warning("dead-lettered source=%s seq=%s terminal status=%d body=%s",
                    source_id, sequence, status, reason)
        return True

    def run_worker(self, poll_interval_s: float = 0.25) -> None:
        LOG.info("spool worker started")
        while not self._stop.is_set():
            processed = self.process_once()
            if not processed:
                self._stop.wait(poll_interval_s)
        LOG.info("spool worker stopped")

    def stop(self) -> None:
        self._stop.set()

    # -- MQTT callbacks ----------------------------------------------------
    def on_connect(self, client, _userdata, _flags, rc: int) -> None:
        if rc != 0:
            LOG.error("mqtt connect failed rc=%d", rc)
            return
        LOG.info("mqtt connected; subscribing to tv/dev/+/telemetry and .../status")
        client.subscribe([("tv/dev/+/telemetry", 1), ("tv/dev/+/status", 1)])

    def on_message(self, _client, _userdata, msg) -> None:
        source_id = parse_source_from_topic(msg.topic)
        if source_id is None:
            LOG.debug("ignoring topic %s", msg.topic)
            return
        if source_id not in self.tokens:
            LOG.warning("dropping frame from unregistered source %s", source_id)
            return

        payload_raw = msg.payload.decode("utf-8", errors="replace")

        # Status transitions (LWT) become heartbeat events (TV5-15 durability).
        if msg.topic.endswith("/status"):
            try:
                status = json.loads(payload_raw).get("status", "unknown")
            except json.JSONDecodeError:
                status = payload_raw.strip() or "unknown"
            body = {
                "schema_version": "1.0",
                "case_id": self.case_id_default,
                "source_id": source_id,
                "device_id": source_id,
                "event_type": "heartbeat",
                "observed_at": now_iso_utc(),
                "metrics": {"link": status},
            }
            self.spool.enqueue(source_id, body)
            return

        try:
            body = json.loads(payload_raw)
        except json.JSONDecodeError:
            LOG.warning("dropping non-JSON payload from %s", source_id)
            return
        if not isinstance(body, dict):
            LOG.warning("dropping non-object payload from %s", source_id)
            return

        # TV5-03: the payload source_id must match the topic source_id.
        # Otherwise a compromised node with a valid cert could publish to
        # another source's topic and have the bridge re-sign the forgery.
        payload_source = body.get("source_id")
        if payload_source != source_id:
            LOG.error(
                "topic/source mismatch: topic=%s payload=%r; refusing to forward",
                msg.topic, payload_source,
            )
            return

        self.spool.enqueue(source_id, body)


# ---------------------------------------------------------------------------
# TLS material (TV5-02)
# ---------------------------------------------------------------------------
def configure_tls(client, ca_file: str, cert_file: str, key_file: str) -> None:
    """Requires an explicit CA, client certificate, and key. Fails loudly."""
    for label, path in (("CA", ca_file), ("client cert", cert_file), ("client key", key_file)):
        if not path or not Path(path).is_file():
            raise SystemExit(f"MQTT TLS enabled but {label} file not readable: {path!r}")
    client.tls_set(ca_certs=ca_file, certfile=cert_file, keyfile=key_file)
    # No setInsecure equivalent; paho verifies server cert against ca_certs by default.


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Traceveil MQTT-to-HTTP bridge")
    parser.add_argument("--broker-host", default=os.getenv("TV_MQTT_HOST", "127.0.0.1"))
    parser.add_argument("--broker-port", type=int, default=int(os.getenv("TV_MQTT_PORT", "8883")))
    parser.add_argument("--broker-tls", action="store_true", default=os.getenv("TV_MQTT_TLS", "1") == "1")
    parser.add_argument("--api-base", default=os.getenv("TV_API_BASE", "http://127.0.0.1:8000/api/v1"))
    parser.add_argument("--case-id", type=int, default=int(os.getenv("TV_DEFAULT_CASE_ID", "1")))
    parser.add_argument("--spool-path", default=os.getenv("TV_SPOOL_PATH", "./bridge_spool.sqlite"))
    parser.add_argument("--log-level", default=os.getenv("TV_LOG_LEVEL", "INFO"))
    args = parser.parse_args()

    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    if mqtt is None:  # pragma: no cover
        raise SystemExit("paho-mqtt is not installed; pip install -r requirements.txt")

    tokens = load_source_tokens(os.getenv("LIVE_SOURCE_TOKENS", ""))
    LOG.info("loaded %d source tokens", len(tokens))

    spool = Spool(Path(args.spool_path))
    depth, dead = spool.depth()
    if depth or dead:
        LOG.warning("spool contains %d pending frames and %d dead-lettered", depth, dead)

    client = mqtt.Client(client_id="traceveil-bridge", clean_session=False)

    if args.broker_tls:
        ca_file = os.getenv("TV_MQTT_CA_FILE", "")
        cert_file = os.getenv("TV_MQTT_CLIENT_CERT", "")
        key_file = os.getenv("TV_MQTT_CLIENT_KEY", "")
        configure_tls(client, ca_file, cert_file, key_file)

    bridge = Bridge(
        api_base=args.api_base,
        tokens=tokens,
        case_id_default=args.case_id,
        spool=spool,
        mqtt_client=client,
    )
    client.on_connect = bridge.on_connect
    client.on_message = bridge.on_message

    worker = threading.Thread(target=bridge.run_worker, name="spool-worker", daemon=True)
    worker.start()

    def _stop(_signum, _frame):
        LOG.info("stopping bridge")
        bridge.stop()
        client.disconnect()
        worker.join(timeout=5)
        spool.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    LOG.info("connecting to broker %s:%d tls=%s", args.broker_host, args.broker_port, args.broker_tls)
    client.connect(args.broker_host, args.broker_port, keepalive=30)
    client.loop_forever()


if __name__ == "__main__":  # pragma: no cover
    main()
