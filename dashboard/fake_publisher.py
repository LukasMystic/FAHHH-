"""Fake ESP32 publisher for the FAHHH? dashboard.

Publishes the topics and payloads defined in contracts/C3_mqtt.md (v3) so the
dashboard can be tested before the real firmware sends data. It walks through
the same route as William's sketch: choose line and destination, RFID
checkpoint, wait for the train, board, arrive, alight, then starts again.
Edge warnings, tilt advisories, sensor dropouts and (rarely) a help request
happen at random along the way.

It follows the C2 rules: an edge warning only clears after a valid distance
reading, and a help request stays active (EMERGENCY) until an explicit
ACK HELP demo reset, which this script only does when asked to.
Like the firmware (PubSubClient), it publishes at QoS 0; only the Last Will is QoS 1.

Usage:
    python fake_publisher.py                      # normal run, heartbeat every 2 s
    python fake_publisher.py --fast               # heartbeat every 1 s, journey runs faster
    python fake_publisher.py --dry-run            # print payloads, do not connect
    python fake_publisher.py --name gebi          # client id fahhh-fake-gebi
    python fake_publisher.py --help-at 20         # press help 20 s after start (test scenario)
    python fake_publisher.py --ack-help-after 30  # simulate someone typing ACK HELP 30 s later
    python fake_publisher.py --no-random-help     # no random help requests
"""

import argparse
import json
import random
import threading
import time

from mqtt_common import DEVICE_ID, T_EVENTS, T_ONLINE, T_STATUS, load_config, make_client

STATUS_EVERY_S = 2
CONNECT_TIMEOUT_S = 10

# Demo stations, same as the sketch (C3 v3)
LINES = {
    "A": ["A01", "A02", "A03", "A04", "A05", "A06"],
    "B": ["B01", "B02", "B03", "B04"],
}

# Route steps: (state, how many heartbeats it lasts, event + source sent on entry)
JOURNEY = [
    ("SELECT_LINE", 3, None),
    ("SELECT_DEST", 3, None),
    ("SEEK_PLATFORM", 6, None),
    ("WAIT_TRAIN", 6, ("CHECKPOINT", "RFID_PHYSICAL")),
    ("WAIT_TRAIN", 3, ("SIM_TRAIN_NEAR", "POTENTIOMETER_BLE_STANDIN")),
    ("ON_TRAIN", 10, ("BOARDING_CONFIRMED_BY_USER", "encoder_button")),
    ("ARRIVING", 4, ("SIM_DESTINATION_APPROACH", "SERIAL_SIMULATED_TRAIN_TELEMETRY")),
    ("COMPLETE", 4, ("ALIGHTING_CONFIRMED_BY_USER", "encoder_button")),
]

EDGE_CHANCE = 0.06       # per heartbeat, outside the train
TILT_CHANCE = 0.03
NO_ECHO_CHANCE = 0.03
MPU_FAULT_CHANCE = 0.015
HELP_CHANCE = 0.004      # rare


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
        # PubSubClient can only publish at QoS 0 (C3); retained still works
        c.publish(prefix + T_ONLINE, "1", qos=0, retain=True)
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


class FakeCane:
    """Holds the same variables the sketch reports in device/status."""

    def __init__(self, publish):
        self.publish = publish
        self.start = time.time()
        self.distance = 95.0      # cm to the ground, cane held normally
        self.tilt = 20.0
        self.edge = False
        self.edge_beats = 0
        self.no_echo_beats = 0
        self.mpu_fault_beats = 0
        self.help = False
        self.help_since = None
        self.state = "SELECT_LINE"
        self.station = ""
        self.dest = ""
        self.train_near = False

    def uptime(self):
        return int(time.time() - self.start)

    def dist_value(self):
        return -1 if self.no_echo_beats > 0 else round(self.distance)

    def event(self, name, source):
        self.publish(T_EVENTS, {
            "device_id": DEVICE_ID, "uptime_s": self.uptime(), "event": name,
            "state": self.state, "source": source, "distance_cm": self.dist_value(),
        }, qos=0)  # PubSubClient: QoS 0 only (C3)

    def change_state(self, new, source):
        if new == self.state:
            return
        self.state = new
        self.event(new, source)  # the sketch's changeState() also emits an event named after the state

    def status(self):
        self.publish(T_STATUS, {
            "device_id": DEVICE_ID, "uptime_s": self.uptime(), "state": self.state,
            "distance_cm": self.dist_value(), "tilt_deg": -1 if self.mpu_fault_beats > 0 else round(self.tilt),
            "edge": int(self.edge), "train_near": int(self.train_near), "help": int(self.help),
            "station": self.station, "dest": self.dest,
        }, qos=0)

    def sensors(self):
        """Random walk for distance and tilt, plus random hazards."""
        # drift back towards a normal grip (~25°) so a tilt advisory does not stick
        self.tilt = min(80.0, max(5.0, self.tilt + (25 - self.tilt) * 0.25 + random.uniform(-4, 4)))
        self.distance = min(140.0, max(70.0, self.distance + random.uniform(-6, 6)))

        if self.no_echo_beats > 0:
            self.no_echo_beats -= 1
        elif random.random() < NO_ECHO_CHANCE:
            self.no_echo_beats = random.randint(1, 2)
            self.event("EDGE_SENSOR_FAULT", "HC_SR04")

        if self.mpu_fault_beats > 0:
            self.mpu_fault_beats -= 1
        elif random.random() < MPU_FAULT_CHANCE:
            self.mpu_fault_beats = random.randint(1, 3)
            self.event("MPU_FAULT_RAW_FALLBACK", "MPU6050")

        if self.edge:
            self.edge_beats -= 1
            # C2: a sensor fault never clears an active warning; only a valid reading does
            if self.edge_beats <= 0 and self.no_echo_beats == 0:
                self.edge = False
                self.distance = random.uniform(85, 105)
                self.event("EDGE_CLEAR", "HC_SR04")
        elif (self.no_echo_beats == 0 and self.state not in ("ON_TRAIN", "ARRIVING")
              and random.random() < EDGE_CHANCE):
            self.edge = True
            self.edge_beats = random.randint(1, 3)
            self.distance = random.uniform(125, 140)  # ground drops away
            self.event("EDGE_WARNING", "HC_SR04")

        if random.random() < TILT_CHANCE:
            self.tilt = random.uniform(66, 75)
            self.event("CANE_TILT_ADVISORY", "MPU6050")

    def press_help(self):
        self.help = True
        self.help_since = time.time()
        self.change_state("EMERGENCY", "physical_help_button_long_press")
        self.event("HELP_REQUEST", "physical_help_button_long_press")

    def ack_help(self):
        """Same as typing ACK HELP in the sketch's Serial Monitor: a demo reset, not proof help arrived."""
        print("[sim] ACK HELP typed: demo reset as in C2 (not proof that help arrived)")
        self.help = False
        self.help_since = None
        self.change_state("SELECT_LINE", "SERIAL_DEMO_RESET")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--name", default="stanley", help="your name, used in the client id")
    parser.add_argument("--fast", action="store_true", help="heartbeat every 1 s")
    parser.add_argument("--dry-run", action="store_true", help="print payloads only")
    parser.add_argument("--help-at", type=float, metavar="SEC",
                        help="press the help button this many seconds after start")
    parser.add_argument("--ack-help-after", type=float, metavar="SEC",
                        help="simulate ACK HELP this many seconds after a help request "
                             "(default: help stays active until you stop the script)")
    parser.add_argument("--no-random-help", action="store_true", help="never press help at random")
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

    cane = FakeCane(publish)
    started = time.time()
    help_done = False
    print("Ctrl+C to stop.")
    try:
        while True:
            line = random.choice(list(LINES))
            stations = LINES[line]
            start_i = random.randrange(0, len(stations) - 1)
            dest_i = random.randrange(start_i + 1, len(stations))
            cane.station, cane.dest, cane.train_near = "", "", False
            restarted = False

            for state, beats, entry_event in JOURNEY:
                if state == "SEEK_PLATFORM":
                    cane.dest = stations[dest_i]
                if entry_event and entry_event[0] == "CHECKPOINT":
                    cane.station = stations[start_i]
                if entry_event and entry_event[0] == "SIM_TRAIN_NEAR":
                    cane.train_near = True
                if state == "ON_TRAIN":
                    cane.train_near = False
                if state == "ARRIVING":
                    cane.station = stations[dest_i]

                # Same order as the sketch: checkpoint() sends CHECKPOINT before changing state;
                # boarding/arriving/alighting change state first, then send their event.
                source = entry_event[1] if entry_event else "encoder_button"
                if entry_event and entry_event[0] == "CHECKPOINT":
                    cane.event(*entry_event)
                cane.change_state(state, source)
                if entry_event and entry_event[0] != "CHECKPOINT":
                    cane.event(*entry_event)

                for _ in range(beats):
                    cane.sensors()
                    if (args.help_at is not None and not help_done and time.time() - started >= args.help_at) \
                            or (not args.no_random_help and random.random() < HELP_CHANCE):
                        help_done = True
                        cane.press_help()
                    if cane.help:
                        # C2: EMERGENCY is latched. The journey pauses; sensors and status keep going.
                        while cane.help:
                            cane.status()
                            time.sleep(every)
                            cane.sensors()
                            if args.ack_help_after is not None and time.time() - cane.help_since >= args.ack_help_after:
                                cane.ack_help()
                        restarted = True  # the sketch restarts at SELECT_LINE after ACK HELP
                        break
                    cane.status()
                    time.sleep(every)
                if restarted:
                    break
    except KeyboardInterrupt:
        print("\nstopping")
    finally:
        if client:
            client.publish(prefix + T_ONLINE, "0", qos=0, retain=True).wait_for_publish(2)
            client.disconnect()
            client.loop_stop()


if __name__ == "__main__":
    main()
