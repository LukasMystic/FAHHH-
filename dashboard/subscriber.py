"""MQTT subscriber for the FAHHH? dashboard.

Subscribes to sic8/fahhh/device/# (contracts/C3_mqtt.md, v3), checks every
message, keeps recent data in memory for the dashboard and appends every
valid message to a CSV log (evidence for testing, report section 10/11).

Run on its own to watch and log messages without the dashboard:
    python subscriber.py
"""

import csv
import json
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path

from mqtt_common import DEVICE_ID, T_EVENTS, T_ONLINE, T_STATUS, load_config, make_client

DATA_DIR = Path(__file__).parent / "data"
CSV_FIELDS = ["received_at", "topic", "device_id", "uptime_s", "event", "state", "source", "distance_cm",
              "tilt_deg", "edge", "train_near", "help", "station", "dest"]
STALE_AFTER_S = 6  # no status for 3 heartbeats (2 s each) -> treat as no data


class TelemetryStore:
    """Thread-safe store: MQTT thread writes, dashboard reads."""

    def __init__(self, max_points=600, log_path=None):
        self.lock = threading.Lock()
        self.status = deque(maxlen=max_points)   # dicts with received_at
        self.events = deque(maxlen=200)
        self.online = None                       # True / False / None (unknown)
        self.broker_connected = False
        self.last_status_at = None
        self.rejected = 0                        # messages that failed validation
        self.log_path = log_path
        if log_path:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(log_path, "w", newline="") as f:
                csv.DictWriter(f, CSV_FIELDS).writeheader()

    def _log(self, topic, row):
        if not self.log_path:
            return
        with open(self.log_path, "a", newline="") as f:
            csv.DictWriter(f, CSV_FIELDS, extrasaction="ignore").writerow({"topic": topic, **row})

    def handle(self, topic_suffix, payload: bytes):
        """Validate one message and store it. Returns the stored row or None."""
        now = datetime.now()
        if topic_suffix == T_ONLINE:
            value = payload.decode(errors="ignore").strip()
            if value not in ("0", "1"):
                with self.lock:
                    self.rejected += 1
                return None
            with self.lock:
                self.online = value == "1"
            row = {"received_at": now.isoformat(timespec="seconds"), "state": "ONLINE" if value == "1" else "OFFLINE"}
            self._log(topic_suffix, row)
            return row

        row = parse_payload(payload)
        if row is None or (topic_suffix == T_EVENTS and not row.get("event")):
            with self.lock:
                self.rejected += 1
            return None
        row["received_at"] = now.isoformat(timespec="seconds")
        row["_t"] = now
        with self.lock:
            if topic_suffix == T_STATUS:
                self.status.append(row)
                self.last_status_at = now
                # A fresh, valid status proves the cane is alive, even after a
                # retained or Last Will "0" on device/online.
                self.online = True
            elif topic_suffix == T_EVENTS:
                self.events.append(row)
        self._log(topic_suffix, row)
        return row

    def snapshot(self):
        """Copy of current data for the dashboard."""
        with self.lock:
            age = (datetime.now() - self.last_status_at).total_seconds() if self.last_status_at else None
            return {
                "status": list(self.status),
                "events": list(self.events),
                "online": self.online,
                "broker_connected": self.broker_connected,
                "status_age_s": age,
                "stale": age is None or age > STALE_AFTER_S,
                "rejected": self.rejected,
            }


def _num(value):
    """C3: numbers that are not available are sent as -1 (or missing)."""
    if value is None:
        return None
    value = float(value)
    return None if value < 0 else value


def _flag(value):
    return bool(int(value)) if value not in (None, "") else False


def parse_payload(payload: bytes):
    """Check a C3 v3 JSON payload. The broker is public, so ignore anything that doesn't fit."""
    try:
        data = json.loads(payload.decode())
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or data.get("device_id") != DEVICE_ID:
        return None
    try:
        return {
            "device_id": data["device_id"],
            "uptime_s": int(data["uptime_s"]),
            "state": str(data["state"]).upper(),
            "event": str(data.get("event") or "").upper(),
            "source": str(data.get("source") or ""),
            "distance_cm": _num(data.get("distance_cm")),
            "tilt_deg": _num(data.get("tilt_deg")),
            "edge": _flag(data.get("edge")),
            "train_near": _flag(data.get("train_near")),
            "help": _flag(data.get("help")),
            "station": str(data.get("station") or "").upper(),
            "dest": str(data.get("dest") or "").upper(),
        }
    except (KeyError, TypeError, ValueError):
        return None


def start_subscriber(store: TelemetryStore, client_id="fahhh-dash-stanley", verbose=False):
    """Connect in a background thread and feed messages into the store."""
    cfg = load_config()
    prefix = cfg["prefix"]
    client = make_client(cfg, client_id)

    def on_connect(c, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            print(f"[mqtt] connect failed: {reason_code}")
            return
        with store.lock:
            store.broker_connected = True
        c.subscribe(prefix + "device/#", qos=1)
        print(f"[mqtt] connected to {cfg['host']}:{cfg['port']}, subscribed to {prefix}device/#")

    def on_disconnect(c, userdata, flags, reason_code, properties):
        with store.lock:
            store.broker_connected = False
        print(f"[mqtt] disconnected: {reason_code} (reconnecting)")

    def on_message(c, userdata, msg):
        if not msg.topic.startswith(prefix):
            return
        suffix = msg.topic[len(prefix):]
        row = store.handle(suffix, msg.payload)
        if verbose:
            mark = "<-" if row is not None else "!! ignored"
            print(f"{mark} {msg.topic} {msg.payload.decode(errors='replace')}")

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.connect_async(cfg["host"], cfg["port"], keepalive=30)
    client.loop_start()
    return client


def new_log_path():
    return DATA_DIR / f"messages_{datetime.now():%Y%m%d_%H%M%S}.csv"


def main():
    store = TelemetryStore(log_path=new_log_path())
    client = start_subscriber(store, client_id="fahhh-sub-stanley", verbose=True)
    print(f"Logging to {store.log_path}. Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nstopping")
    finally:
        client.disconnect()
        client.loop_stop()


if __name__ == "__main__":
    main()
