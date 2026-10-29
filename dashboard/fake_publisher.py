"""Fake ESP32 publisher for the FAHHH? dashboard.

Publishes the topics and payloads defined in contracts/C3_mqtt.md (v4) so the
dashboard can be tested without Wokwi. It replays the same journey as the
firmware (firmware/sketch.ino, PR #12): choose a destination, checkpoint tags
to the origin platform, the train checks, boarding by the door tag, arrival,
the destination platform tag and the exit, then it starts again. Now and then
it taps a wrong tag first (wrong platform, or the door tag before boarding is
ready). Edge warnings, tilt advisories and sensor faults happen at random.

It follows the C2 rules the way the firmware implements them:
- an edge warning only clears after valid readings, never because of a sensor fault;
- the door tag and the destination platform tag are only accepted with no edge and
  no ultrasonic fault; an edge or fault after BOARDING_READY sends BOARDING_CANCELLED,
  and BOARDING_READY comes back once it is clear;
- a help request stays active (EMERGENCY) until an explicit ACK HELP demo reset,
  which this script only does when asked to; the journey then restarts at SELECT_DEST.
Like the firmware (PubSubClient), it publishes at QoS 0; only the Last Will is QoS 1.

Usage:
    python fake_publisher.py                      # normal run, heartbeat every 2 s
    python fake_publisher.py --fast               # heartbeat every 1 s, journey runs faster
    python fake_publisher.py --dry-run            # print payloads, do not connect
    python fake_publisher.py --name gebi          # client id fahhh-fake-gebi
    python fake_publisher.py --help-at 20         # press help 20 s after start (test scenario)
    python fake_publisher.py --ack-help-after 30  # simulate someone typing ACK HELP 30 s later
    python fake_publisher.py --no-random-help     # no random help requests
    python fake_publisher.py --no-wrong-tags      # never tap a wrong tag or meet a wrong train
    python fake_publisher.py --seed 1             # same random run every time
"""

import argparse
import json
import random
import threading
import time

from mqtt_common import DEVICE_ID, T_EVENTS, T_ONLINE, T_STATUS, load_config, make_client

STATUS_EVERY_S = 2
CONNECT_TIMEOUT_S = 10

# Demo stations, same as the firmware (C3 v4)
ORIGIN = "DEMO_A"
DESTINATIONS = ["DEMO_B", "DEMO_C"]

# Sources the firmware uses (C3 v4)
TAG = "RFID_PHYSICAL"            # card tapped on the reader
TYPED_TAG = "SERIAL_SIMULATION"  # SIM TAG <node> in Serial (junctions have no card)
TRAIN = "SERIAL_TRAIN_SIMULATION"
BEACON = "POTENTIOMETER_BLE_STANDIN"

EDGE_CHANCE = 0.06       # per heartbeat, not while riding the train
TILT_CHANCE = 0.03
NO_ECHO_CHANCE = 0.03
MPU_FAULT_CHANCE = 0.015
HELP_CHANCE = 0.004      # rare
WRONG_TAG_CHANCE = 0.35  # per place where a wrong tag or wrong train can happen


class Restart(Exception):
    """ACK HELP reset the journey; start again at SELECT_DEST."""


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
    """Holds the same variables the firmware reports, and follows its rules."""

    def __init__(self, publish, rng):
        self.publish = publish
        self.rng = rng
        self.start = time.time()
        self.distance = 95.0      # cm to the ground, cane held normally
        self.tilt = 20.0
        self.edge = False
        self.edge_beats = 0
        self.no_echo_beats = 0
        self.mpu_fault_beats = 0
        self.help = False
        self.help_since = None
        self.state = "SELECT_DEST"
        self.station = ""
        self.dest = ""
        self.train_near = False
        self.train_ok = False     # matched, stopped and door open (Serial simulation)
        self.boarding_ready = False

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
        self.event(new, source)  # the firmware's changeState() also emits an event named after the state

    def status(self):
        self.publish(T_STATUS, {
            "device_id": DEVICE_ID, "uptime_s": self.uptime(), "state": self.state,
            "distance_cm": self.dist_value(), "tilt_deg": -1 if self.mpu_fault_beats > 0 else round(self.tilt),
            "edge": int(self.edge), "train_near": int(self.train_near), "help": int(self.help),
            "station": self.station, "dest": self.dest,
        }, qos=0)

    def refresh_ready(self, source):
        """Same check as refreshBoardingReady() in the firmware."""
        ready = (self.state == "WAIT_TRAIN" and self.train_near and self.train_ok
                 and not self.edge and self.no_echo_beats == 0)
        if ready == self.boarding_ready:
            return
        self.boarding_ready = ready
        self.event("BOARDING_READY" if ready else "BOARDING_CANCELLED", source)

    def reset(self, source):
        """resetJourney(): back to SELECT_DEST, nothing chosen yet."""
        self.station, self.dest = "", ""
        self.train_near = self.train_ok = self.boarding_ready = False
        self.change_state("SELECT_DEST", source)

    def sensors(self):
        """Random walk for distance and tilt, plus random hazards and faults."""
        # drift back towards a normal grip (~25°) so a tilt advisory does not stick
        self.tilt = min(80.0, max(5.0, self.tilt + (25 - self.tilt) * 0.25 + self.rng.uniform(-4, 4)))
        self.distance = min(140.0, max(70.0, self.distance + self.rng.uniform(-6, 6)))

        if self.no_echo_beats > 0:
            self.no_echo_beats -= 1
            if self.no_echo_beats == 0:
                self.event("EDGE_SENSOR_RECOVERED", "HC_SR04")
                self.refresh_ready("HC_SR04_RECOVERED")
        elif self.rng.random() < NO_ECHO_CHANCE:
            self.no_echo_beats = self.rng.randint(1, 2)
            self.event("EDGE_SENSOR_FAULT", "HC_SR04")
            self.refresh_ready("HC_SR04_FAULT")

        if self.mpu_fault_beats > 0:
            self.mpu_fault_beats -= 1
            if self.mpu_fault_beats == 0:
                self.event("MPU_RECOVERED", "MPU6050")
        elif self.rng.random() < MPU_FAULT_CHANCE:
            self.mpu_fault_beats = self.rng.randint(1, 3)
            self.event("MPU_FAULT_RAW_FALLBACK", "MPU6050")

        if self.edge:
            self.edge_beats -= 1
            # C2: a sensor fault never clears an active warning; only valid readings do
            if self.edge_beats <= 0 and self.no_echo_beats == 0:
                self.edge = False
                self.distance = self.rng.uniform(85, 105)
                self.event("EDGE_CLEAR", "HC_SR04")
                self.refresh_ready("HC_SR04_EDGE_CLEAR")
        elif self.no_echo_beats == 0 and self.state != "ON_TRAIN" and self.rng.random() < EDGE_CHANCE:
            self.edge = True
            self.edge_beats = self.rng.randint(1, 3)
            self.distance = self.rng.uniform(125, 140)  # ground drops away
            # like the firmware: raw distance while the MPU fails or the cane is tilted past 65°
            raw = self.mpu_fault_beats > 0 or self.tilt > 65
            self.event("EDGE_WARNING", "HC_SR04_RAW_FALLBACK" if raw else "HC_SR04_MPU6050")
            self.refresh_ready("HC_SR04_EDGE")

        if self.mpu_fault_beats == 0 and self.rng.random() < TILT_CHANCE:
            self.tilt = self.rng.uniform(66, 75)
            self.event("CANE_TILT_ADVISORY", "MPU6050")

    def press_help(self):
        self.help = True
        self.help_since = time.time()
        self.change_state("EMERGENCY", "physical_help_button_long_press")
        self.event("HELP_REQUEST", "physical_help_button_long_press")
        if self.train_near:  # the beacon only counts while waiting for the train
            self.train_near = False
            self.refresh_ready(BEACON)

    def ack_help(self):
        """Same as typing ACK HELP in the firmware's Serial Monitor: a demo reset, not proof help arrived."""
        print("[sim] ACK HELP typed: demo reset as in C2 (not proof that help arrived)")
        self.help = False
        self.help_since = None
        self.reset("SERIAL_DEMO_RESET")


class Runner:
    """Heartbeats, random hazards and help handling between journey steps."""

    def __init__(self, cane, every, args):
        self.cane = cane
        self.every = every
        self.args = args
        self.started = time.time()
        self.help_done = False

    def beats(self, n):
        cane = self.cane
        for _ in range(n):
            cane.sensors()
            due = (self.args.help_at is not None and not self.help_done
                   and time.time() - self.started >= self.args.help_at)
            if due or (not self.args.no_random_help and cane.rng.random() < HELP_CHANCE):
                self.help_done = True
                cane.press_help()
            if cane.help:
                # C2: EMERGENCY is latched. The journey pauses; sensors and status keep going.
                while cane.help:
                    cane.status()
                    time.sleep(self.every)
                    cane.sensors()
                    if (self.args.ack_help_after is not None
                            and time.time() - cane.help_since >= self.args.ack_help_after):
                        cane.ack_help()
                raise Restart
            cane.status()
            time.sleep(self.every)

    def until(self, condition):
        """Wait heartbeat by heartbeat, e.g. until an edge has cleared."""
        while not condition():
            self.beats(1)


def journey(cane, run, wrong_tags):
    """One trip from DEMO_A to DEMO_B or DEMO_C, in the firmware's order of events."""
    rng = cane.rng

    def maybe(name, source):
        if wrong_tags and rng.random() < WRONG_TAG_CHANCE:
            cane.event(name, source)
            run.beats(2)

    run.beats(3)                                        # choosing with the knob
    cane.dest = rng.choice(DESTINATIONS)
    cane.change_state("SEEK_PLATFORM", "encoder_button")
    run.beats(3)

    # Origin route: entrance card, junction typed in Serial, platform card
    for node, source in (("A_MASUK", TAG), ("A_SIMPANG", TYPED_TAG), ("A_PLATFORM", TAG)):
        if node == "A_PLATFORM":
            maybe("CHECKPOINT_REJECTED", TAG)           # wrong platform first
        cane.station = ORIGIN
        cane.event("CHECKPOINT", source)
        if node == "A_PLATFORM":
            cane.change_state("WAIT_TRAIN", source)
        run.beats(3)

    # Train comes in (beacon and train data are simulated in Wokwi)
    cane.train_near = True
    cane.event("SIM_TRAIN_NEAR", BEACON)
    cane.refresh_ready(BEACON)
    run.beats(1)
    maybe("CHECKPOINT_REJECTED", TAG)                   # door tag before boarding is ready
    maybe("TRAIN_REJECTED", TRAIN)                      # another train first
    for name in ("TRAIN_MATCH", "TRAIN_STOPPED", "TRAIN_DOOR_OPEN"):
        if name == "TRAIN_DOOR_OPEN":
            cane.train_ok = True
        cane.event(name, TRAIN)
        cane.refresh_ready(TRAIN)
        run.beats(1)

    # Door tag inside the train: only accepted while boarding is ready
    run.until(lambda: cane.boarding_ready)
    cane.train_near = cane.train_ok = cane.boarding_ready = False
    cane.change_state("ON_TRAIN", TAG)
    cane.event("BOARDING_CONFIRMED_BY_TAG", TAG)
    run.beats(8)

    # Arrival: train data, then the destination platform card, the junction, the exit card
    cane.change_state("ARRIVING", TRAIN)
    cane.event("SIM_DESTINATION_APPROACH", TRAIN)
    run.beats(2)
    for name in ("TRAIN_STOPPED", "TRAIN_DOOR_OPEN"):
        cane.event(name, TRAIN)
        run.beats(1)
    run.until(lambda: not cane.edge and cane.no_echo_beats == 0)
    cane.station = cane.dest
    cane.event("CHECKPOINT", TAG)                       # destination platform: stepped off
    run.beats(3)
    cane.event("CHECKPOINT", TYPED_TAG)                 # destination junction
    run.beats(3)
    cane.event("CHECKPOINT", TAG)                       # exit
    cane.change_state("COMPLETE", TAG)
    run.beats(4)
    cane.reset("encoder_long_press_reset")              # knob held to start a new trip


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
    parser.add_argument("--no-wrong-tags", action="store_true", help="never tap a wrong tag or meet a wrong train")
    parser.add_argument("--seed", type=int, help="random seed, for a repeatable run")
    args = parser.parse_args()

    cfg = load_config()
    prefix = cfg["prefix"]
    every = 1 if args.fast else STATUS_EVERY_S
    client = None if args.dry_run else connect(cfg, f"fahhh-fake-{args.name}", prefix)

    def publish(topic, payload, qos):
        text = json.dumps(payload, separators=(",", ":"))
        if len(text) >= 200:
            print(f"[warn] payload is {len(text)} bytes; C3 limit is 200")
        print(f"-> {prefix}{topic} {text}")
        if client:
            client.publish(prefix + topic, text, qos=qos)

    cane = FakeCane(publish, random.Random(args.seed))
    run = Runner(cane, every, args)
    print("Ctrl+C to stop.")
    try:
        while True:
            try:
                journey(cane, run, wrong_tags=not args.no_wrong_tags)
            except Restart:
                pass  # ACK HELP: like the firmware, start again at SELECT_DEST
    except KeyboardInterrupt:
        print("\nstopping")
    finally:
        if client:
            client.publish(prefix + T_ONLINE, "0", qos=0, retain=True).wait_for_publish(2)
            client.disconnect()
            client.loop_stop()


if __name__ == "__main__":
    main()
