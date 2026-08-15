"""Controlled Phase 3 HTTP telemetry simulator; it never touches external devices."""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def request_json(url: str, method: str = "GET", body: dict | None = None, token: str | None = None) -> dict:
    headers = {"Accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body).encode(); headers["Content-Type"] = "application/json"
    if token:
        headers["X-Traceveil-Source-Token"] = token
    try:
        with urlopen(Request(url, data=data, method=method, headers=headers), timeout=10) as response:
            return json.loads(response.read())
    except HTTPError as exc:
        raise SystemExit(f"HTTP {exc.code}: {exc.read().decode(errors='replace')}") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="Send controlled normal, malformed, heartbeat, or suspicious live telemetry.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/api/v1")
    parser.add_argument("--case-id", type=int)
    parser.add_argument("--source-id", default="live-lab-01")
    parser.add_argument("--token", default="traceveil-demo-token")
    parser.add_argument("--scenario", choices=["normal", "heartbeat", "malformed", "suspicious", "reconnect"], default="normal")
    parser.add_argument("--count", type=int, default=12)
    parser.add_argument("--interval", type=float, default=0.15)
    args = parser.parse_args()
    case_id = args.case_id
    if case_id is None:
        created = request_json(f"{args.base_url}/cases", "POST", {"name": "Phase 3 live demonstration", "description": "Controlled HTTP simulator case", "owner": "Local investigator"})
        case_id = int(created["id"])
    session = request_json(f"{args.base_url}/cases/{case_id}/live-sessions", "POST", {"label": f"{args.scenario.title()} simulator", "source_ids": [args.source_id], "stale_after_seconds": 30})
    print(f"case={case_id} session={session['session_id']} scenario={args.scenario}")
    count = max(1, args.count)
    for sequence in range(count):
        event_type = "heartbeat" if args.scenario == "heartbeat" else "telemetry"
        metrics: dict[str, object] = {"temperature_c": round(21.5 + sequence * 0.1, 2), "online": True}
        if args.scenario == "suspicious":
            event_type = "authentication"; metrics = {"action": "authenticate", "outcome": "failed", "attempt": sequence + 1}
        payload = {"schema_version": "1.0", "case_id": case_id, "source_id": args.source_id, "device_id": "sim-device-01", "event_type": event_type, "observed_at": datetime.now(timezone.utc).isoformat(), "sequence": sequence, "metrics": metrics if event_type == "telemetry" or args.scenario == "suspicious" else {}}
        if args.scenario == "malformed" and sequence == 0:
            payload.pop("observed_at")
        receipt = request_json(f"{args.base_url}/live/telemetry", "POST", payload, args.token)
        print(json.dumps(receipt, sort_keys=True))
        if args.scenario == "reconnect" and sequence == count // 2:
            print("simulated transport pause; SSE clients replay from Last-Event-ID")
            time.sleep(2)
        time.sleep(max(0, args.interval))
    print(f"Review http://localhost:5173/live?case={case_id}")


if __name__ == "__main__":
    main()
