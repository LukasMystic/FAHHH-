# C3 · MQTT topics and payload

| | |
|---|---|
| **Owner** | Stanley |
| **Used by** | William (firmware publishes), Stanley (dashboard subscribes) |
| **Due** | Mon 26 Oct, 18:00 |
| **Status** | DRAFT v2 — event names and P2 fields wait for C2 and the P2 scope decision |

Only the owner edits this file. Changes after publishing: `CONTRACT CHANGE C3` + 👍 from all four.

## Principle

MQTT **only reports**, one way: ESP32 → broker → dashboard. Every safety alert is decided and fired on the ESP32 first (P3). If Wi-Fi or the broker is down, alerts still work; MQTT messages are simply skipped.

No dashboard → device commands in Stage 2 (e.g. *companion acknowledges emergency*). That goes to report section 14, Pengembangan Lanjutan.

## Broker

| | |
|---|---|
| Broker | HiveMQ Cloud (Serverless, free) |
| Port | 8883 (TLS) |
| Credentials | Shared privately by Stanley. Firmware: `firmware/secrets.h`. Dashboard: `dashboard/.env`. Never committed. |
| Topic prefix | `sic8/fahhh/` |
| Fallback if TLS fails in Wokwi | `broker.hivemq.com`, port 1883, no login (public, test only — agree in group before switching) |

**Client IDs** (must be unique, or the broker kicks the older one off):

| Client | Client ID |
|---|---|
| ESP32 in Wokwi | `fahhh-esp32-unit-01` |
| Fake publisher | `fahhh-fake-<name>` (e.g. `fahhh-fake-stanley`) |
| Dashboard | `fahhh-dash-<name>` |

## Topics

| Topic | Direction | When | QoS | Retained |
|---|---|---|---|---|
| `sic8/fahhh/device/events` | ESP32 → broker | On every event (state change, button) | 1 | no |
| `sic8/fahhh/device/status` | ESP32 → broker | Every 2 s (heartbeat) | 0 | no |
| `sic8/fahhh/device/online` | ESP32 → broker | `"1"` after connect; `"0"` as Last Will | 1 | **yes** |

`device/online` lets the dashboard show *device offline* when Wokwi stops or Wi-Fi drops (useful for an abnormal test scenario).

## Payloads (JSON)

Keep each message **under 256 bytes** (PubSubClient's default buffer) — compact JSON, no spaces needed.

### `device/events`

```json
{"device_id":"unit-01","uptime_s":132,"event":"LEVEL_CHANGE","state":"WARNING","distance_cm":42,"battery":87}
```

### `device/status`

```json
{"device_id":"unit-01","uptime_s":135,"state":"NORMAL","distance_cm":118,"battery":87}
```

| Field | Type | In | Required | Notes |
|---|---|---|---|---|
| `device_id` | string | both | yes | `unit-01` for the demo |
| `uptime_s` | int | both | yes | `millis()/1000`. No NTP needed; the dashboard stamps the receive time itself. |
| `event` | string | events | yes | One of the event names below |
| `state` | string | both | yes | Current state name from C2, `UPPER_SNAKE_CASE` |
| `distance_cm` | number | both | if a distance sensor exists | Latest reading; `-1` = sensor error / no echo |
| `battery` | int | both | yes | 0–100 (%). Simulated with a potentiometer in Wokwi. |
| *(P2 fields)* | — | — | — | Added after the P2 scope is decided Mon 26 (e.g. `heading_deg`, `route_step`) |

**Rules for both sides**
- The dashboard ignores fields it does not know and treats missing optional fields as empty — so adding a field never breaks anything.
- Names: topics lowercase; JSON keys `snake_case`; `event` and `state` values `UPPER_SNAKE_CASE`.

## Event names

Final list comes from C2 (William). Current candidates:

| Event | Feature | Meaning |
|---|---|---|
| `BOARDING_GAP` | P1 | Gap/step between platform and train detected |
| `GUIDE_STEP` | P2 | Next guidance instruction given |
| `ARRIVED_PLATFORM` | P2 | Route finished |
| `LEVEL_CHANGE` | S1 | Drop-off / stairs / platform edge ahead |
| `EMERGENCY` | S2 | Emergency button pressed |
| `LOW_BATTERY` | — | Battery below threshold |
| `SENSOR_ERROR` | — | Sensor gives no reading (abnormal test case) |

## Test without the ESP32

`dashboard/fake_publisher.py` publishes exactly these topics and payloads, so the dashboard can be built before the firmware is ready.

## Decisions in this draft (Stanley, Sun 25 Oct)

| Topic | Decision | Why |
|---|---|---|
| Broker | HiveMQ Cloud, TLS 8883; public `broker.hivemq.com:1883` only as agreed fallback | Private + meets the guideline; fallback keeps William unblocked |
| Direction | One way (device → dashboard) | Smaller scope for 5 days; downlink is future work |
| Heartbeat | Every 2 s | Live chart looks responsive in the demo video |
| Time | `uptime_s` from the ESP32, dashboard stamps arrival time | No NTP code, one less failure point in Wokwi |

## Reference: connecting the ESP32 in Wokwi (for William)

Not part of the contract, just a starting point. Libraries: `PubSubClient`, `ArduinoJson` (add both in Wokwi's Library Manager).

```cpp
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include "secrets.h"

WiFiClientSecure net;
PubSubClient mqtt(net);

const char* T_EVENTS = "sic8/fahhh/device/events";
const char* T_STATUS = "sic8/fahhh/device/status";
const char* T_ONLINE = "sic8/fahhh/device/online";

void connectMqtt() {
  if (WiFi.status() != WL_CONNECTED || mqtt.connected()) return;
  // Last Will: broker publishes "0" (retained) if we drop off
  if (mqtt.connect("fahhh-esp32-unit-01", MQTT_USER, MQTT_PASS,
                   T_ONLINE, 1, true, "0")) {
    mqtt.publish(T_ONLINE, "1", true);
  }
}

void setup() {
  Serial.begin(115200);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD, 6);   // Wokwi-GUEST, channel 6 connects faster
  net.setInsecure();                          // demo only: skips certificate check
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
}

void loop() {
  // 1. read sensors + fire alerts FIRST (never wait for MQTT, P3)
  // 2. then report:
  connectMqtt();          // non-blocking: skip if no Wi-Fi
  mqtt.loop();
  // every 2 s: mqtt.publish(T_STATUS, json);   on event: mqtt.publish(T_EVENTS, json);
}
```

Notes: `connectMqtt()` must not loop or block, or alerts would wait for the network. Retry at most every few seconds (track `millis()`). `setInsecure()` is acceptable for the Wokwi demo; the report should mention that a real device would verify HiveMQ's certificate.
