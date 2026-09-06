#!/usr/bin/env python3
"""TV5-02 / TV5-14: real end-to-end bridge test over mutual TLS.

Unlike the in-process unit tests, this starts the ACTUAL bridge.py
process, connected to a real mosquitto broker with client certificates,
and proves the whole path:

    ESP32 (esp32-lab-01 client cert)
      --mqtt/TLS--> broker --> bridge.py (tv-bridge client cert)
      --HTTP--> fake backend (records the POST, returns 202)
      --mqtt/TLS ACK--> tv/dev/esp32-lab-01/ack --> back to the device

Assertions:
  * the fake backend received exactly the forwarded frame, with the
    correct X-Traceveil-Source-Token and matching source_id/sequence;
  * the device received an ACK on its own ack topic with that sequence.

Assumes the broker is already running (tests/step5/start_broker.sh) and
the lab PKI exists (tests/step5/generate_lab_pki.sh). Exit 0 on success.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import paho.mqtt.client as mqtt

HERE = Path(__file__).resolve().parent
PKI = HERE / "pki"
BRIDGE_DIR = HERE.parent.parent / "hardware" / "mqtt_bridge"

SOURCE = "esp32-lab-01"
TOKEN = "tok-esp32-lab-01"


# --- fake backend ------------------------------------------------------------
class _Recorder:
    def __init__(self):
        self.posts: list[dict] = []
        self.lock = threading.Lock()


def _make_handler(recorder: _Recorder):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_a):  # silence
            pass

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8", errors="replace")
            with recorder.lock:
                recorder.posts.append({
                    "path": self.path,
                    "token": self.headers.get("X-Traceveil-Source-Token"),
                    "body": body,
                })
            self.send_response(202)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"queued"}')

    return Handler


def _make_client(client_id: str):
    try:
        from paho.mqtt.client import CallbackAPIVersion
        return mqtt.Client(CallbackAPIVersion.VERSION2, client_id=client_id)
    except (ImportError, AttributeError):
        return mqtt.Client(client_id=client_id)


def main() -> int:
    for f in ("ca.crt", "tv-bridge.crt", "tv-bridge.key",
              f"{SOURCE}.crt", f"{SOURCE}.key"):
        if not (PKI / f).is_file():
            print(f"missing PKI file {f}; run generate_lab_pki.sh first", file=sys.stderr)
            return 2

    recorder = _Recorder()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(recorder))
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()

    # Start the real bridge process.
    env = dict(os.environ)
    env.update({
        "LIVE_SOURCE_TOKENS": json.dumps({SOURCE: TOKEN}),
        "TV_API_BASE": f"http://127.0.0.1:{port}/api/v1",
        "TV_MQTT_HOST": "127.0.0.1",
        "TV_MQTT_PORT": "8883",
        "TV_MQTT_TLS": "1",
        "TV_MQTT_CA_FILE": str(PKI / "ca.crt"),
        "TV_MQTT_CLIENT_CERT": str(PKI / "tv-bridge.crt"),
        "TV_MQTT_CLIENT_KEY": str(PKI / "tv-bridge.key"),
        "TV_SPOOL_PATH": "/tmp/tv_real_bridge_spool.sqlite",
        "TV_DEFAULT_CASE_ID": "1",
        "TV_LOG_LEVEL": "INFO",
    })
    if os.path.exists(env["TV_SPOOL_PATH"]):
        os.remove(env["TV_SPOOL_PATH"])

    bridge = subprocess.Popen(
        [sys.executable, "bridge.py"],
        cwd=str(BRIDGE_DIR), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )

    acks: list[dict] = []
    device = _make_client("test-esp32-lab-01")
    device.tls_set(ca_certs=str(PKI / "ca.crt"),
                   certfile=str(PKI / f"{SOURCE}.crt"),
                   keyfile=str(PKI / f"{SOURCE}.key"))

    def on_message(_c, _u, msg):
        try:
            acks.append(json.loads(msg.payload.decode()))
        except Exception:
            pass

    device.on_message = on_message

    try:
        # Give the bridge a moment to connect and subscribe.
        time.sleep(3)
        device.connect("127.0.0.1", 8883, keepalive=30)
        device.loop_start()
        device.subscribe(f"tv/dev/{SOURCE}/ack", qos=1)
        time.sleep(1)

        frame = {
            "schema_version": "1.0", "case_id": 1, "source_id": SOURCE,
            "device_id": SOURCE, "event_type": "telemetry",
            "observed_at": "2026-09-05T10:00:00+00:00", "sequence": 1,
            "metrics": {"temperature_c": 24.5},
        }
        device.publish(f"tv/dev/{SOURCE}/telemetry", json.dumps(frame), qos=1)

        deadline = time.time() + 15
        while time.time() < deadline:
            with recorder.lock:
                got_post = bool(recorder.posts)
            if got_post and acks:
                break
            time.sleep(0.2)
    finally:
        device.loop_stop()
        try:
            device.disconnect()
        except Exception:
            pass
        bridge.terminate()
        try:
            bridge.wait(timeout=5)
        except subprocess.TimeoutExpired:
            bridge.kill()
        server.shutdown()

    # --- assertions ----------------------------------------------------------
    ok = True
    with recorder.lock:
        posts = list(recorder.posts)

    if not posts:
        print("FAIL: bridge did not forward any frame to the backend", file=sys.stderr)
        print("--- bridge output ---", file=sys.stderr)
        print(bridge.stdout.read() if bridge.stdout else "", file=sys.stderr)
        return 1

    post = posts[0]
    if not post["path"].endswith("/live/telemetry"):
        print(f"FAIL: unexpected POST path {post['path']!r}", file=sys.stderr); ok = False
    if post["token"] != TOKEN:
        print(f"FAIL: wrong token forwarded: {post['token']!r}", file=sys.stderr); ok = False
    body = json.loads(post["body"])
    if body.get("source_id") != SOURCE or body.get("sequence") != 1:
        print(f"FAIL: forwarded body mismatch: {body}", file=sys.stderr); ok = False

    if not acks:
        print("FAIL: device never received a backend ACK", file=sys.stderr); ok = False
    elif acks[0].get("sequence") != 1:
        print(f"FAIL: ACK sequence mismatch: {acks[0]}", file=sys.stderr); ok = False

    if ok:
        print("real_bridge_test: OK (forwarded frame + token + ACK verified over mTLS)")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
