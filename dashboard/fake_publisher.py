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
import random
import threading
import time

from mqtt_common import DEVICE_ID, T_EVENTS, T_ONLINE, T_STATUS, load_config, make_client

STATUS_EVERY_S = 2
CONNECT_TIMEOUT_S = 10

# Candidate events from C3 (final list comes from C2): event -> (state, weight).
# Weights keep the demo believable: emergencies and sensor errors are rare.
EVENTS = {
    "LEVEL_CHANGE": ("WARNING", 30),
    "BOARDING_GAP": ("WARNING", 25),
    "GUIDE_STEP": ("GUIDING", 30),
    "ARRIVED_PLATFORM": ("NORMAL", 8),
    "SENSOR_ERROR": ("ERROR", 4),
    "EMERGENCY": ("EMERGENCY", 3),
}
EVENT_CHANCE = 0.25        # chance of an event per heartbeat
STATE_HOLD_BEATS = (1, 3)  # how many heartbeats a non-normal state lasts


def connect(cfg, client_id, prefix):
    client = make_client(cfg, client_id)
    connected = threading.Event()
    # Last Will: broker publishes "0" if we disappear (C3 device/online)
    client.will_set(prefix + T_ONLINE, "0", qos=1, retain=True)

    def on_connect(c, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            print(f"[mqtt] connect failed: {reason_code}")
            return
        print(f"[mqtt] connected to {cfg['host']}:{cfg['port']} as {client_id}")
        c.publish(prefix + T_ONLINE, "1", qos=1, retain=True)
        connected.set()

    def on_disconnect(c, userdata, flags, reason_code, properties):
        connected.clear()
        print(f"[mqtt] disconnected: {reason_code}")

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.connect_async(cfg["host"], cfg["port"], keepalive=30)
    client.loop_start()
    # Do not publish before the connection is up (first messages could be lost)
    if not connected.wait(CONNECT_TIMEOUT_S):
        client.loop_stop()
        raise SystemExit(f"[mqtt] could not connect to {cfg['host']}:{cfg['port']} within {CONNECT_TIMEOUT_S} s")
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
    client = None if args.dry_run else connect(cfg, f"fahhh-fake-{args.name}", prefix)

    def publish(topic, payload, qos):
        text = json.dumps(payload, separators=(",", ":"))
        if len(text) >= 256:
            print(f"[warn] payload is {len(text)} bytes; C3 limit is 256")
        print(f"-> {prefix}{topic} {text}")
        if client:
            client.publish(prefix + topic, text, qos=qos)

    names = list(EVENTS)
    weights = [EVENTS[n][1] for n in names]
    start = time.time()
    battery = 100.0
    distance = 120.0
    state, hold = "NORMAL", 0
    low_battery_sent = False
    print("Ctrl+C to stop.")
    try:
        while True:
            uptime = int(time.time() - start)
            battery = max(0.0, battery - random.uniform(0.05, 0.3))
            distance = min(300.0, max(5.0, distance + random.uniform(-25, 25)))

            if hold > 0:
                hold -= 1
                if hold == 0:
                    state = "NORMAL"
            elif random.random() < EVENT_CHANCE:
                event = random.choices(names, weights)[0]
                state = EVENTS[event][0]
                hold = random.randint(*STATE_HOLD_BEATS) if state != "NORMAL" else 0
                publish(T_EVENTS, {
                    "device_id": DEVICE_ID, "uptime_s": uptime, "event": event, "state": state,
                    "distance_cm": -1 if state == "ERROR" else round(distance),
                    "battery": round(battery),
                }, qos=1)

            if battery < 20 and not low_battery_sent:
                low_battery_sent = True
                publish(T_EVENTS, {
                    "device_id": DEVICE_ID, "uptime_s": uptime, "event": "LOW_BATTERY", "state": state,
                    "distance_cm": -1 if state == "ERROR" else round(distance),
                    "battery": round(battery),
                }, qos=1)

            publish(T_STATUS, {
                "device_id": DEVICE_ID, "uptime_s": uptime, "state": state,
                # while the sensor is in error there is no valid reading (C3: -1)
                "distance_cm": -1 if state == "ERROR" else round(distance),
                "battery": round(battery),
            }, qos=0)
            time.sleep(every)
    except KeyboardInterrupt:
        print("\nstopping")
    finally:
        if client:
            client.publish(prefix + T_ONLINE, "0", qos=1, retain=True).wait_for_publish(2)
            client.disconnect()
            client.loop_stop()


if __name__ == "__main__":
    main()
