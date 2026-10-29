# C3 · MQTT topics and payload

| | |
|---|---|
| **Owner** | Stanley |
| **Used by** | William (firmware publishes), Stanley (dashboard subscribes) |
| **Due** | Mon 26 Oct, 18:00 |
| **Status** | **DRAFT v4** (`CONTRACT CHANGE C3`, Thu 29 Oct): brings C3 in line with the firmware merged in PR #12. Needs 👍 from all four. v3 was published Tue 27 Oct (PR #6) |

Only the owner edits this file. Changes after publishing: `CONTRACT CHANGE C3` + 👍 from all four.

## What changed in v4

The firmware (`firmware/sketch.ino`, PR #12) is the source of truth; v4 only describes what it already sends. Topics, broker, QoS and payload fields are **unchanged**.

| | v3 | v4 |
|---|---|---|
| Stations | A01–A06, B01–B04 (two demo lines) | `DEMO_A` (origin), `DEMO_B` / `DEMO_C` (destinations), fictional |
| States | Starts at `SELECT_LINE` | `SELECT_LINE` removed; starts at `SELECT_DEST` |
| Boarding / alighting | `BOARDING_CONFIRMED_BY_USER`, `ALIGHTING_CONFIRMED_BY_USER` (knob press) | Removed. Boarding is `BOARDING_CONFIRMED_BY_TAG` (door tag read inside the train after the train checks pass); stepping off is the destination platform tag (`CHECKPOINT`) |
| New events | | `CHECKPOINT_REJECTED`, `TRAIN_MATCH`, `TRAIN_REJECTED`, `TRAIN_STOPPED`, `TRAIN_MOVING`, `TRAIN_DOOR_OPEN`, `TRAIN_DOOR_CLOSED`, `BOARDING_READY`, `BOARDING_CANCELLED`, `BOARDING_CONFIRMED_BY_TAG`, `EDGE_SENSOR_RECOVERED`, `MPU_RECOVERED` |
| `station` field | Last RFID station ID | Last confirmed **station** (`DEMO_A`, then the destination); checkpoint names stay in Serial |
| Reference code | Illustration for William | Removed: the firmware now implements it (see "Implementation") |

## Principle

MQTT **only reports**, one way: ESP32 → broker → dashboard. Every safety alert is decided and fired on the ESP32 first (P3). If Wi-Fi or the broker is down, alerts still work; MQTT messages are simply skipped.

All Wi-Fi and MQTT work runs in its own FreeRTOS task, separate from the sensor and alert loop; the loop only hands JSON to a queue without waiting. The aim is that connecting or a slow network does not hold up a reading or an alert. **Measured in the connectivity test sketch** (Tue 27 Oct, `tests/results/2026-10-27_wokwi-connectivity.md`): `loopMaxMs` stayed 1–3 ms during 6–7 s TLS connects. The firmware prints the same `loopMaxMs` in its 5 s Serial status; the report only claims it for the cane after test T7b.

No dashboard → device commands in Stage 2 (e.g. *companion acknowledges emergency*). That goes to report section 14, Pengembangan Lanjutan.

## Broker

| | |
|---|---|
| Broker | **HiveMQ public broker** — `broker.hivemq.com` |
| Port | **8883** (MQTT over TLS) · 1883 plain TCP only for quick local tests |
| Login | None (public broker has no username/password) |
| Topic prefix | `sic8/fahhh/` |
| Decided | Mon 26 Oct, all four agreed |

**Why not HiveMQ Cloud:** free Serverless clusters can no longer be created, and the Starter trial needs a credit card and ends after 15 days (before judging ends). The report explains this in section 8.2 and lists a private HiveMQ Cloud cluster with logins in section 14.

**Because the broker is public:** anyone can read or publish on any topic. So: demo data only, no personal data; the dashboard must ignore messages it can't parse; client IDs must be unique worldwide (below).

**Client IDs** (must be unique, or the broker kicks the older one off):

| Client | Client ID |
|---|---|
| ESP32 in Wokwi | `fahhh-esp32-unit-01` |
| Fake publisher | `fahhh-fake-<name>` (e.g. `fahhh-fake-stanley`) |
| Dashboard | `fahhh-dash-<name>` |

## Topics

| Topic | Direction | When | QoS | Retained |
|---|---|---|---|---|
| `sic8/fahhh/device/events` | ESP32 → broker | Every time the sketch calls `event()` | 0 | no |
| `sic8/fahhh/device/status` | ESP32 → broker | Every 2 s (heartbeat) | 0 | no |
| `sic8/fahhh/device/online` | ESP32 → broker | `"1"` after connect (QoS 0); `"0"` as Last Will (QoS 1) | 0 / 1 | **yes** |

`device/online` lets the dashboard show *device offline* when Wokwi stops or Wi-Fi drops (useful for an abnormal test scenario). A fresh `device/status` also counts as online, so a stale `"0"` never hides live data.

### Delivery: QoS 0, and what that means

The firmware uses PubSubClient, which [can only publish at QoS 0](https://github.com/knolleary/pubsubclient#limitations). Only the Last Will is sent at QoS 1. So:

- An event can be **lost** if the connection drops at that moment, and events are dropped (not queued) while the cane is offline. The dashboard's event list can have gaps.
- The **current situation is not lost**: every 2 s `device/status` repeats the state and the `edge` and `help` flags. After a lost event or a reconnect, the dashboard shows the right state again within one heartbeat.
- Safety never depends on delivery: the cane has already sounded the alert locally (P3). MQTT only tells the companion.

The report (8.2) must describe it this way and must not promise guaranteed event delivery. QoS 1 publishing would need another library (e.g. `espMqttClient`); listed as future work in section 14.

## Payloads (JSON)

Keep each JSON payload **under 200 bytes**: compact JSON, no spaces. PubSubClient's buffer must hold the whole packet (header + topic + JSON); the firmware sets `setBufferSize(384)`. With v4 names the longest event is about 155 bytes and the longest status about 165 bytes. Numbers that are not available (`NAN` in the sketch) are sent as `-1`.

### `device/events`

One message per `event(name, source)` call in the sketch.

```json
{"device_id":"unit-01","uptime_s":132,"event":"CHECKPOINT_REJECTED","state":"SEEK_PLATFORM","source":"RFID_PHYSICAL","distance_cm":21}
```

### `device/status`

```json
{"device_id":"unit-01","uptime_s":135,"state":"WAIT_TRAIN","distance_cm":21,"tilt_deg":12,"edge":0,"train_near":1,"help":0,"station":"DEMO_A","dest":"DEMO_B"}
```

| Field | Type | In | Sketch variable | Notes |
|---|---|---|---|---|
| `device_id` | string | both | — | `unit-01` for the demo |
| `uptime_s` | int | both | `millis()/1000` | No NTP needed; the dashboard stamps the receive time itself |
| `event` | string | events | `name` in `event()` | One of the event names below |
| `state` | string | both | `stateName(state)` | One of the states below |
| `source` | string | events | `source` in `event()` | What caused it; see "Sources" below |
| `distance_cm` | number | both | `distanceCm` | Distance to the ground, tilt-corrected; raw while the MPU6050 fails or the cane is tilted past 65°; `-1` = no valid reading |
| `tilt_deg` | number | status | `tiltDeg` | Cane tilt from vertical; `-1` = MPU6050 not readable |
| `edge` | 0/1 | status | `edge` | 1 while an edge warning is active |
| `train_near` | 0/1 | status | `trainNear` | 1 while waiting and the door beacon (potentiometer stand-in) is near; back to 0 after boarding |
| `help` | 0/1 | status | `help` | 1 while a help request is active |
| `station` | string | status | `lastStation` | `""` until the first origin checkpoint; then `DEMO_A` (also while on the train); the destination ID once its platform tag is confirmed |
| `dest` | string | status | `destStationId()` | `DEMO_B` or `DEMO_C` after the knob press confirms it; `""` before |

**Battery is not in C3** (dropped in v3). Nothing in the circuit measures or simulates it, so no made-up value is sent.

**Rules for both sides**
- The dashboard ignores fields it does not know and treats missing fields as empty, so adding a field never breaks anything.
- Names: topics lowercase; JSON keys `snake_case`; `event` and `state` values `UPPER_SNAKE_CASE`, exactly as printed on Serial.

## States (from the firmware)

| State | Meaning |
|---|---|
| `SELECT_DEST` | Start, or after a reset: the user chooses the destination (`DEMO_B` / `DEMO_C`) with the knob |
| `SEEK_PLATFORM` | Route confirmed with a knob press; walking to the origin platform, checkpoint tag by checkpoint tag |
| `WAIT_TRAIN` | The origin platform tag was read in the right order; waiting for the train |
| `ON_TRAIN` | The door tag inside the train (`TRAIN_INSIDE`) was read after all boarding checks passed |
| `ARRIVING` | Serial `SIM ARRIVE` for the chosen destination; covers the train stopping, the doors opening, the destination platform tag and the walk to the exit |
| `COMPLETE` | The last exit checkpoint was read |
| `EMERGENCY` | Help button held for 3 s. Latched until the demo-only Serial `ACK HELP`, which restarts the journey at `SELECT_DEST` |

Every state change also arrives as an event named after the new state (`changeState()` calls `event()`).

The firmware also has journey phases (`TO_ORIGIN_PLATFORM`, `AT_ORIGIN_PLATFORM`, …) and checkpoint names (`A_MASUK`, `A_P1_WAIT`, `TRAIN_INSIDE`, …). Those appear only in Serial, not in MQTT.

## Event names (from the firmware)

**Safety (S1, S2)**

| Event | Feature | When | Source |
|---|---|---|---|
| `EDGE_WARNING` | S1, P1 | Distance to the ground jumps by > 15 cm (and > 25 cm) for 3 readings: edge or step ahead | `HC_SR04_MPU6050` (tilt-corrected) or `HC_SR04_RAW_FALLBACK` |
| `EDGE_CLEAR` | S1 | Distance back to normal for 0.7 s | `HC_SR04` |
| `EDGE_SENSOR_FAULT` | S1 | Ultrasonic sensor gives no echo. An active edge warning is not cleared by a fault | `HC_SR04` |
| `EDGE_SENSOR_RECOVERED` | S1 | Echo is back after a fault | `HC_SR04` |
| `MPU_FAULT_RAW_FALLBACK` | S1 | MPU6050 not readable; edge detection keeps running on the raw distance | `MPU6050` |
| `MPU_RECOVERED` | S1 | MPU6050 readable again | `MPU6050` |
| `CANE_TILT_ADVISORY` | S1 | Cane tilted more than 65° for 2 s | `MPU6050` |
| `HELP_REQUEST` | S2 | Help button held for 3 s | `physical_help_button_long_press` |

**Route to the platform and out of the destination (P2)**

| Event | Feature | When | Source |
|---|---|---|---|
| `CHECKPOINT` | P2 | A checkpoint tag was read in the expected order (origin route, destination platform, exit route) | `RFID_PHYSICAL` or `SERIAL_SIMULATION` |
| `CHECKPOINT_REJECTED` | P2, P1 | A tag that does not fit the route: wrong platform, wrong order, the door tag before boarding is ready, the destination platform tag before the train has stopped with its doors open, or a card that is not registered. Re-reading the last accepted tag is ignored (Serial only) | `RFID_PHYSICAL`, `SERIAL_SIMULATION` or `RFID_UNREGISTERED` |

**Train and boarding (P1), simulated through Serial and the potentiometer**

| Event | Feature | When | Source |
|---|---|---|---|
| `SIM_TRAIN_NEAR` | P1 | Door beacon near while waiting (potentiometer above about 2600 ADC) | `POTENTIOMETER_BLE_STANDIN` |
| `TRAIN_MATCH` | P1 | `SIM TRAIN TRAIN01 <side> <dest>` matches the platform side and destination | `SERIAL_TRAIN_SIMULATION` |
| `TRAIN_REJECTED` | P1 | `SIM TRAIN …` does not match (wrong train, side or destination) | `SERIAL_TRAIN_SIMULATION` |
| `TRAIN_STOPPED` / `TRAIN_MOVING` | P1 | `SIM STOPPED` / `SIM MOVING` | `SERIAL_TRAIN_SIMULATION` |
| `TRAIN_DOOR_OPEN` / `TRAIN_DOOR_CLOSED` | P1 | `SIM DOOR OPEN\|CLOSE <side>` on the right side | `SERIAL_TRAIN_SIMULATION` |
| `BOARDING_READY` | P1 | All boarding checks pass: beacon near, train matched, stopped, door open on the right side, no edge, no ultrasonic fault | whatever completed the checks: `SERIAL_TRAIN_SIMULATION`, `POTENTIOMETER_BLE_STANDIN`, `HC_SR04_EDGE_CLEAR` or `HC_SR04_RECOVERED` |
| `BOARDING_CANCELLED` | P1 | A check stops passing after `BOARDING_READY` (door closes, train moves, beacon far, edge, ultrasonic fault) | `SERIAL_TRAIN_SIMULATION`, `POTENTIOMETER_BLE_STANDIN`, `HC_SR04_EDGE` or `HC_SR04_FAULT` |
| `BOARDING_CONFIRMED_BY_TAG` | P1 | Door tag inside the train read while boarding is ready; state becomes `ON_TRAIN` | `RFID_PHYSICAL` or `SERIAL_SIMULATION` |
| `SIM_DESTINATION_APPROACH` | P1, P2 | `SIM ARRIVE <dest>` while on the train; state becomes `ARRIVING` | `SERIAL_TRAIN_SIMULATION` |

**State names**: every state change, see above. Sources: `encoder_button` (route confirmed), `encoder_long_press_reset` (knob held > 1.2 s), `SERIAL_DEMO_RESET` (`ACK HELP`), `physical_help_button_long_press`, or the tag or simulation that caused it.

**Sources that mean "simulated"**: `SERIAL_SIMULATION` (a tag typed as `SIM TAG`), `SERIAL_TRAIN_SIMULATION` (train data typed in Serial), `POTENTIOMETER_BLE_STANDIN` (the potentiometer standing in for BLE RSSI). The dashboard shows the source with each event, so simulated steps stay visible as simulated.

Sensor faults are sent as events when they happen and also show up in `device/status` as `distance_cm: -1` / `tilt_deg: -1` while they last.

## Demo stations (from the firmware)

| ID | Role | Notes |
|---|---|---|
| `DEMO_A` | Origin | Fictional station: entrance, junction, platforms P1/P2 |
| `DEMO_B` | Destination | Fictional; chosen with the knob or `SIM DEST B` |
| `DEMO_C` | Destination | Fictional; chosen with the knob or `SIM DEST C` |

The dashboard uses this list to show station names. If the firmware's list changes, this table changes with it. Card UIDs and the commands for each checkpoint are in `tests/test_scenarios.md`.

## Test without the ESP32

`dashboard/fake_publisher.py` publishes exactly these topics and payloads and replays the same journey as the firmware (checkpoints, a wrong tag now and then, train checks, boarding by tag, arrival, exit), so the dashboard can be tested without Wokwi.

## Implementation (firmware)

The firmware implements this contract in `firmware/sketch.ino`: `queueMqttJson()`, `queueMqttEvent()`, `queueMqttStatus()`, `mqttTask()` and `startMqttTask()`. The rules it follows:

- `loop()` and `event()` never call `mqtt.connect()`, `mqtt.loop()` or `mqtt.publish()`. All Wi-Fi and MQTT work happens in one FreeRTOS task on core 0; the sensor and alert code only hands JSON to a queue of 8 with zero wait.
- While offline, messages are dropped, not queued (see "Delivery").
- Each Wi-Fi join gets 15 s before it is restarted; MQTT connect is retried every 5 s; `setBufferSize(384)`, `setSocketTimeout(5)`, `setKeepAlive(30)`.
- Last Will `"0"` on `device/online` (QoS 1, retained); `"1"` retained after each connect.
- `setInsecure()` is acceptable for the Wokwi demo; the report should mention that a real device would verify the broker's certificate and use a private broker with logins.

Still to measure in the firmware: `loopMaxMs` while connecting and while the broker is unreachable (T7b), and the time to *Offline* and back to *Online* with keep-alive 30 (T7a). Keep the Wokwi tab visible while testing: a background tab slows the simulation and can trigger a disconnect.

## Decisions

| Topic | Decision | Why |
|---|---|---|
| Broker | HiveMQ public broker, TLS 8883, no login (team decision Mon 26) | Free, no card, no trial end; keeps HiveMQ as in the guideline |
| Direction | One way (device → dashboard) | Smaller scope for 5 days; downlink is future work |
| Heartbeat | Every 2 s | Live chart looks responsive in the demo video |
| Time | `uptime_s` from the ESP32, dashboard stamps arrival time | No NTP code, one less failure point in Wokwi |
| Names | States and events exactly as the firmware prints them (v3, Tue 27; still true in v4) | The firmware is the source of truth; no renaming layer to keep in sync |
| Battery | Dropped (v3) | Not measured or simulated anywhere in the circuit |
| QoS | 0 for all publishes, Last Will at QoS 1 (v3, PR #6 review) | PubSubClient can only publish at QoS 0; the status heartbeat repeats the current state |
| Network task | Wi-Fi/MQTT in a separate FreeRTOS task on core 0 (v3, PR #6 review); in the firmware since PR #12 | A blocking connect must not delay sensor readings or alerts; firmware measurement is test T7b |
| Keep-alive | `setKeepAlive(30)` (proposed after the connectivity test Tue 27; in the firmware since PR #12) | With the 15 s default, a Wokwi slowdown made the broker drop the cane once; T7a confirms the new timing |
| Stations | `DEMO_A` / `DEMO_B` / `DEMO_C`, fictional (v4, PR #12) | The journey now models one origin station with a route to the platform, and two destinations; no real station data needed |
| Boarding and alighting | Confirmed by tags, not by a knob press (v4, PR #12) | The cane checks the train (simulated) and reads the door tag; stepping off is the destination platform tag |
| `station` field | Station level only (v4) | Checkpoint names change with the route style (flat, lift, ramp) and stay in Serial; the dashboard needs where the passenger is, not which tag |
