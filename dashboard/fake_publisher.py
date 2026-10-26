"""Fake ESP32 publisher for the FAHHH? dashboard.

Publishes the topics and payloads defined in contracts/C3_mqtt.md so the
dashboard can be built before the real firmware sends data.

Usage:
    python fake_publisher.py               # normal run, heartbeat every 2 s
    python fake_publisher.py --fast        # heartbeat every 1 s
    python fake_publisher.py --dry-run     # print payloads, do not connect
    python fake_publisher.py --name gebi   # client id fahhh-fake-gebi
"""

import argparse
import json
import os
import random
import ssl
import time

from dotenv import load_dotenv

DEVICE_ID = "unit-01"
STATUS_EVERY_S = 2

# Candidate events from C3; final list comes from C2.
EVENTS = {
    "BOARDING_GAP": "WARNING",
    "LEVEL_CHANGE": "WARNING",
    "GUIDE_STEP": "GUIDING",
    "ARRIVED_PLATFORM": "NORMAL",
    "EMERGENCY": "EMERGENCY",
    "SENSOR_ERROR": "ERROR",
}


def load_config():
    load_dotenv()  # optional: defaults are the HiveMQ public broker (C3)
    prefix = os.getenv("TOPIC_PREFIX", "sic8/fahhh/")
    if not prefix.endswith("/"):
        prefix += "/"
    return {
        "host": os.getenv("MQTT_HOST", "broker.hivemq.com"),
        "port": int(os.getenv("MQTT_PORT", "8883")),
        "user": os.getenv("MQTT_USER", ""),
        "password": os.getenv("MQTT_PASS", ""),
        "prefix": prefix,
    }


def connect(cfg, client_id, prefix):
    import paho.mqtt.client as mqtt

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
    if cfg["user"]:
        client.username_pw_set(cfg["user"], cfg["password"])
    if cfg["port"] == 8883:
        client.tls_set(tls_version=ssl.PROTOCOL_TLS_CLIENT)
    # Last Will: broker publishes "0" if we disappear (C3 device/online)
    client.will_set(prefix + "device/online", "0", qos=1, retain=True)

    def on_connect(c, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            print(f"[mqtt] connect failed: {reason_code}")
            return
        print(f"[mqtt] connected to {cfg['host']}:{cfg['port']} as {client_id}")
        c.publish(prefix + "device/online", "1", qos=1, retain=True)

    def on_disconnect(c, userdata, flags, reason_code, properties):
        print(f"[mqtt] disconnected: {reason_code}")

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.connect(cfg["host"], cfg["port"], keepalive=30)
    client.loop_start()
    return client


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--name", default="stanley", help="your name, used in the client id")
    parser.add_argument("--fast", action="store_true", help="heartbeat every 1 s")
    parser.add_argument("--dry-run", action="store_true", help="print payloads only")
    args = parser.parse_args()

    cfg = load_config()
    prefix = cfg["prefix"]
    every = 1 if args.fast else STATUS_EVERY_S
    client = None

    if not args.dry_run:
        client = connect(cfg, f"fahhh-fake-{args.name}", prefix)

    def publish(topic, payload, qos):
        text = json.dumps(payload, separators=(",", ":"))
        if len(text) >= 256:
            print(f"[warn] payload is {len(text)} bytes; C3 limit is 256")
        print(f"-> {prefix}{topic} {text}")
        if client:
            client.publish(prefix + topic, text, qos=qos)

    start = time.time()
    battery = 100.0
    state = "NORMAL"
    distance = 120.0
    print("Ctrl+C to stop.")
    try:
        while True:
            uptime = int(time.time() - start)
            battery = max(0.0, battery - random.uniform(0.05, 0.3))
            distance = min(300.0, max(5.0, distance + random.uniform(-25, 25)))

            # roughly one event every 3 heartbeats
            if random.random() < 0.33:
                event = random.choice(list(EVENTS))
                state = EVENTS[event]
                dist = -1 if event == "SENSOR_ERROR" else round(distance)
                publish("device/events", {
                    "device_id": DEVICE_ID, "uptime_s": uptime, "event": event,
                    "state": state, "distance_cm": dist, "battery": round(battery),
                }, qos=1)
            elif state != "NORMAL" and random.random() < 0.5:
                state = "NORMAL"

            if battery < 20 and random.random() < 0.2:
                publish("device/events", {
                    "device_id": DEVICE_ID, "uptime_s": uptime, "event": "LOW_BATTERY",
                    "state": state, "distance_cm": round(distance), "battery": round(battery),
                }, qos=1)

            publish("device/status", {
                "device_id": DEVICE_ID, "uptime_s": uptime, "state": state,
                "distance_cm": round(distance), "battery": round(battery),
            }, qos=0)
            time.sleep(every)
    except KeyboardInterrupt:
        print("\nstopping")
    finally:
        if client:
            client.publish(prefix + "device/online", "0", qos=1, retain=True).wait_for_publish(2)
            client.loop_stop()
            client.disconnect()


if __name__ == "__main__":
    main()
