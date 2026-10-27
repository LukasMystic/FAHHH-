# C3 · MQTT topics and payload

| | |
|---|---|
| **Owner** | Stanley |
| **Used by** | William (firmware publishes), Stanley (dashboard subscribes) |
| **Due** | Mon 26 Oct, 18:00 |
| **Status** | DRAFT v3 — names taken from William's sketch (`08a37ec`) and C2 (PR #5); waiting for all four 👍 |

Only the owner edits this file. Changes after publishing: `CONTRACT CHANGE C3` + 👍 from all four.

## Principle

MQTT **only reports**, one way: ESP32 → broker → dashboard. Every safety alert is decided and fired on the ESP32 first (P3). If Wi-Fi or the broker is down, alerts still work; MQTT messages are simply skipped.

All Wi-Fi and MQTT work runs in its own FreeRTOS task, separate from the sensor and alert loop, so connecting or a slow network does not hold up a reading or an alert. This still has to be measured in Wokwi before the report states it (see the notes under the reference code).

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

Keep each message **under 256 bytes** (PubSubClient's default buffer) — compact JSON, no spaces. Numbers that are not available (`NAN` in the sketch) are sent as `-1`.

### `device/events`

One message per `event(name, source)` call in the sketch.

```json
{"device_id":"unit-01","uptime_s":132,"event":"EDGE_WARNING","state":"WAIT_TRAIN","source":"HC_SR04","distance_cm":42}
```

### `device/status`

```json
{"device_id":"unit-01","uptime_s":135,"state":"WAIT_TRAIN","distance_cm":118,"tilt_deg":12,"edge":0,"train_near":0,"help":0,"station":"A01","dest":"A06"}
```

| Field | Type | In | Sketch variable | Notes |
|---|---|---|---|---|
| `device_id` | string | both | — | `unit-01` for the demo |
| `uptime_s` | int | both | `millis()/1000` | No NTP needed; the dashboard stamps the receive time itself |
| `event` | string | events | `name` in `event()` | One of the event names below |
| `state` | string | both | `stateName(state)` | One of the states below |
| `source` | string | events | `source` in `event()` | What caused it, e.g. `HC_SR04`, `encoder_button`, `RFID_PHYSICAL` |
| `distance_cm` | number | both | `distanceCm` | Tilt-corrected distance to the ground; `-1` = no valid reading |
| `tilt_deg` | number | status | `tiltDeg` | Cane tilt from vertical; `-1` = MPU6050 not readable |
| `edge` | 0/1 | status | `edge` | 1 while an edge warning is active |
| `train_near` | 0/1 | status | `trainNear` | 1 while the door beacon (potentiometer stand-in) is near |
| `help` | 0/1 | status | `help` | 1 while a help request is active |
| `station` | string | status | `LINES[lineNo][currentNo].id` | Last RFID checkpoint, `""` if none yet |
| `dest` | string | status | `LINES[lineNo][destNo].id` | Chosen destination, `""` before it is chosen |

**Battery is not in C3 v3.** Nothing in the circuit measures or simulates it, so the team agreed to drop it rather than send a made-up value. (Needs the 👍 with this version.)

**Rules for both sides**
- The dashboard ignores fields it does not know and treats missing fields as empty, so adding a field never breaks anything.
- Names: topics lowercase; JSON keys `snake_case`; `event` and `state` values `UPPER_SNAKE_CASE`, exactly as printed on Serial.

## States (from the sketch)

| State | Meaning |
|---|---|
| `SELECT_LINE` | User is choosing a line with the rotary knob |
| `SELECT_DEST` | User is choosing the destination station |
| `SEEK_PLATFORM` | Route set; waiting for an RFID checkpoint on the way to the platform |
| `WAIT_TRAIN` | At the platform, waiting for the train |
| `ON_TRAIN` | User confirmed boarding |
| `ARRIVING` | Destination is near (simulated train telemetry or destination tag) |
| `COMPLETE` | User confirmed alighting, or tapped the destination checkpoint |
| `EMERGENCY` | Help button held for 3 s |

## Event names (from the sketch)

| Event | Feature | When |
|---|---|---|
| `EDGE_WARNING` | S1, P1 | Distance to the ground jumps by > 15 cm for 3 readings (edge or step ahead) |
| `EDGE_CLEAR` | S1 | Distance back to normal for 0.7 s |
| `CANE_TILT_ADVISORY` | S1 | Cane tilted more than 65° for 2 s |
| `EDGE_SENSOR_FAULT` | S1 | Ultrasonic sensor gives no echo (long beep, like a hazard). An active edge warning is not cleared by a fault |
| `MPU_FAULT_RAW_FALLBACK` | S1 | MPU6050 not readable; edge detection keeps running on the raw distance |
| `HELP_REQUEST` | S2 | Help button held for 3 s |
| `CHECKPOINT` | P2 | An RFID station tag was read |
| `SIM_TRAIN_NEAR` | P1 | Door beacon near while waiting (potentiometer stand-in or Serial `SIM TRAIN`) |
| `BOARDING_CONFIRMED_BY_USER` | P1 | User pressed the knob after the train-near cue |
| `SIM_DESTINATION_APPROACH` | P2 | Serial `SIM ARRIVE <id>` while on the train |
| `ALIGHTING_CONFIRMED_BY_USER` | P1 | User pressed the knob while arriving |
| *any state name* | — | `changeState()` also calls `event(<new state>)`, so every state change arrives as an event with the state's name |

Sensor faults are sent as events when they happen (`EDGE_SENSOR_FAULT`, `MPU_FAULT_RAW_FALLBACK`, from C2) and also show up in `device/status` as `distance_cm: -1` / `tilt_deg: -1` while they last.

## Demo stations (from the sketch)

| Line | Stations |
|---|---|
| Demo A | A01 Jakarta Kota, A02 Jayakarta, A03 Mangga Besar, A04 Sawah Besar, A05 Juanda, A06 Gondangdia |
| Demo B | B01 Tanah Abang, B02 Palmerah, B03 Kebayoran, B04 Pondok Ranji |

The dashboard uses this list to show station names. If the sketch's list changes, this table changes with it.

## Test without the ESP32

`dashboard/fake_publisher.py` publishes exactly these topics and payloads, walking through the same route states as the sketch, so the dashboard can be tested before the firmware sends data.

## Decisions in this draft

| Topic | Decision | Why |
|---|---|---|
| Broker | HiveMQ public broker, TLS 8883, no login (team decision Mon 26) | Free, no card, no trial end; keeps HiveMQ as in the guideline |
| Direction | One way (device → dashboard) | Smaller scope for 5 days; downlink is future work |
| Heartbeat | Every 2 s | Live chart looks responsive in the demo video |
| Time | `uptime_s` from the ESP32, dashboard stamps arrival time | No NTP code, one less failure point in Wokwi |
| Names | States and events exactly as in William's sketch and C2 (v3, Tue 27). The "proposed mapping" to old names in C2 is not used | The firmware is the source of truth; no renaming layer to keep in sync |
| Battery | Dropped (v3) | Not measured or simulated anywhere in the circuit |
| QoS | 0 for all publishes, Last Will at QoS 1 (v3, PR #6 review) | PubSubClient can only publish at QoS 0; the status heartbeat repeats the current state |
| Network task | Wi-Fi/MQTT in a separate FreeRTOS task on core 0 (v3, PR #6 review) | A blocking connect must not delay sensor readings or alerts; to be measured in Wokwi |

## Reference: adding MQTT to the sketch (for William)

Not part of the contract, just a starting point. Library: `PubSubClient` (add `PubSubClient` to `libraries.txt`). No JSON library needed.

```cpp
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include "secrets.h"   // WIFI_SSID, WIFI_PASSWORD, MQTT_HOST, MQTT_PORT

WiFiClientSecure net;
PubSubClient mqtt(net);
const char* T_EVENTS = "sic8/fahhh/device/events";
const char* T_STATUS = "sic8/fahhh/device/status";
const char* T_ONLINE = "sic8/fahhh/device/online";
unsigned long lastMqttTry = 0, lastMqttStatus = 0;

// NAN -> -1 for JSON
float j(float v) { return isfinite(v) ? v : -1; }

void connectMqtt() {                       // call every loop; returns fast
  if (mqtt.connected() || WiFi.status() != WL_CONNECTED) return;
  if (millis() - lastMqttTry < 5000) return;  // retry at most every 5 s
  lastMqttTry = millis();
  if (mqtt.connect("fahhh-esp32-unit-01", nullptr, nullptr, T_ONLINE, 1, true, "0"))
    mqtt.publish(T_ONLINE, "1", true);
}

// Call this at the end of event(name, source)
void publishEvent(const char* name, const char* source) {
  if (!mqtt.connected()) return;           // never block an alert on the network
  char buf[256];
  snprintf(buf, sizeof(buf),
    "{\"device_id\":\"unit-01\",\"uptime_s\":%lu,\"event\":\"%s\",\"state\":\"%s\",\"source\":\"%s\",\"distance_cm\":%.0f}",
    millis() / 1000, name, stateName(state), source, j(distanceCm));
  mqtt.publish(T_EVENTS, buf);
}

// Call every loop; sends every 2 s
void publishStatus() {
  if (!mqtt.connected() || millis() - lastMqttStatus < 2000) return;
  lastMqttStatus = millis();
  const char* station = currentNo >= 0 ? LINES[lineNo][currentNo].id : "";
  const char* dest = state >= SEEK_PLATFORM ? LINES[lineNo][destNo].id : "";
  char buf[256];
  snprintf(buf, sizeof(buf),
    "{\"device_id\":\"unit-01\",\"uptime_s\":%lu,\"state\":\"%s\",\"distance_cm\":%.0f,\"tilt_deg\":%.0f,"
    "\"edge\":%d,\"train_near\":%d,\"help\":%d,\"station\":\"%s\",\"dest\":\"%s\"}",
    millis() / 1000, stateName(state), j(distanceCm), j(tiltDeg),
    edge, trainNear, help, station, dest);
  mqtt.publish(T_STATUS, buf);
}

// setup(): WiFi.begin(WIFI_SSID, WIFI_PASSWORD, 6); net.setInsecure(); mqtt.setServer(MQTT_HOST, MQTT_PORT);
// loop(): after all service*() calls: connectMqtt(); mqtt.loop(); publishStatus();
```

Notes:
- Sensors and alerts run first in `loop()`; MQTT comes after, so a slow network never delays a warning (P3).
- `mqtt.connect()` itself can block for 1–3 s during the TLS handshake. That is why it only retries every 5 s. Mention this limitation in report 8.2; a real device would run MQTT in a separate FreeRTOS task.
- `dest` is only sent from `SEEK_PLATFORM` onward, because before that the user is still choosing (the state order in the `enum` makes `state >= SEEK_PLATFORM` work, except `EMERGENCY`, which is last and also sends the chosen destination).
- `setInsecure()` is acceptable for the Wokwi demo; the report should mention that a real device would verify the broker's certificate and use a private broker with logins.
