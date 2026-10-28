// FAHHH? connectivity test: ESP32 in Wokwi -> HiveMQ public broker -> dashboard.
//
// Stanley's own test project, NOT the team firmware. It checks three things
// before the integration session:
//   1. Wokwi's Wi-Fi can reach broker.hivemq.com over TLS (port 8883).
//   2. The C3 task-based MQTT pattern (William's review of PR #6) runs in Wokwi.
//   3. While the network is busy or down, loop() keeps running on time
//      (loopMaxMs in the [TEST] line every 5 s).
//
// It publishes C3 v3 payloads with made-up values, so the dashboard shows it
// as unit-01. Do not run it at the same time as the real firmware.

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <atomic>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"

#define USE_TLS 1            // 1 = port 8883 with TLS (C3). 0 = port 1883 fallback test.

const char* WIFI_SSID = "Wokwi-GUEST";
const char* WIFI_PASSWORD = "";
const char* MQTT_HOST = "broker.hivemq.com";
const uint16_t MQTT_PORT = USE_TLS ? 8883 : 1883;
const char* CLIENT_ID = "fahhh-esp32-test-stanley";   // not the firmware's id, so both can coexist

const char* T_EVENTS = "sic8/fahhh/device/events";
const char* T_STATUS = "sic8/fahhh/device/status";
const char* T_ONLINE = "sic8/fahhh/device/online";

// ---------------------------------------------------------------- C3 task pattern

enum class TxKind : uint8_t { Event, Status };
struct TxMessage { TxKind kind; char json[256]; };
QueueHandle_t txQueue = nullptr;
std::atomic<bool> mqttReady{false};
std::atomic<uint32_t> published{0}, publishFailed{0}, dropped{0}, connectAttempts{0}, lastConnectMs{0};

// Called only from loop(), never from an ISR. Zero wait.
bool queueJson(TxKind kind, const char* json) {
  if (!txQueue || !mqttReady.load()) { dropped++; return false; }   // drop while offline
  TxMessage m{};
  m.kind = kind;
  int n = snprintf(m.json, sizeof(m.json), "%s", json);
  if (n < 0 || n >= (int)sizeof(m.json)) { dropped++; return false; }
  if (xQueueSend(txQueue, &m, 0) != pdTRUE) { dropped++; return false; }
  return true;
}

void mqttTask(void*) {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD, 6);
#if USE_TLS
  WiFiClientSecure net;
  net.setInsecure();                      // Wokwi demo only
#else
  WiFiClient net;
#endif
  PubSubClient mqtt(net);
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setBufferSize(384);
  mqtt.setSocketTimeout(5);
  TxMessage m{};
  unsigned long lastTry = millis() - 5000UL;
  unsigned long wifiSince = millis();        // when we last started a Wi-Fi attempt
  bool wifiReported = false;

  for (;;) {
    if (WiFi.status() != WL_CONNECTED) {
      mqttReady.store(false);
      wifiReported = false;
      while (xQueueReceive(txQueue, &m, 0) == pdTRUE) {}
      // Give each Wi-Fi attempt 15 s before restarting it (Wokwi needs a few seconds to join)
      if (millis() - wifiSince >= 15000UL) { wifiSince = millis(); WiFi.reconnect(); }
      vTaskDelay(pdMS_TO_TICKS(50));
      continue;
    }
    if (!wifiReported) {
      wifiReported = true;
      Serial.printf("[NET] Wi-Fi connected, IP %s\n", WiFi.localIP().toString().c_str());
    }
    if (!mqtt.connected()) {
      mqttReady.store(false);
      while (xQueueReceive(txQueue, &m, 0) == pdTRUE) {}
      if (millis() - lastTry >= 5000UL) {
        lastTry = millis();
        connectAttempts++;
        Serial.printf("[NET] connecting to %s:%u (%s)...\n", MQTT_HOST, MQTT_PORT, USE_TLS ? "TLS" : "plain");
        unsigned long t0 = millis();
        bool ok = mqtt.connect(CLIENT_ID, nullptr, nullptr, T_ONLINE, 1, true, "0");
        lastConnectMs = millis() - t0;
        if (ok) {
          mqtt.publish(T_ONLINE, "1", true);
          mqttReady.store(true);
          Serial.printf("[NET] MQTT connected in %lu ms\n", (unsigned long)lastConnectMs.load());
        } else {
          Serial.printf("[NET] MQTT connect FAILED after %lu ms, state=%d\n",
                        (unsigned long)lastConnectMs.load(), mqtt.state());
        }
      }
      vTaskDelay(pdMS_TO_TICKS(50));
      continue;
    }
    mqtt.loop();
    if (xQueueReceive(txQueue, &m, 0) == pdTRUE) {
      if (mqtt.publish(m.kind == TxKind::Event ? T_EVENTS : T_STATUS, m.json)) published++;
      else publishFailed++;
    }
    vTaskDelay(pdMS_TO_TICKS(10));
  }
}

void startMqttTask() {
  txQueue = xQueueCreate(8, sizeof(TxMessage));
  if (txQueue) xTaskCreatePinnedToCore(mqttTask, "mqtt", 16384, nullptr, 1, nullptr, 0);
}

// ---------------------------------------------------------------- fake cane data (C3 v3 payloads)

const char* STATES[] = {"SELECT_LINE", "SELECT_DEST", "SEEK_PLATFORM", "WAIT_TRAIN", "ON_TRAIN", "ARRIVING", "COMPLETE"};
int stateIdx = 0;
float distanceCm = 100;
bool edge = false;

void publishEvent(const char* name, const char* source) {
  char buf[256];
  snprintf(buf, sizeof(buf),
    "{\"device_id\":\"unit-01\",\"uptime_s\":%lu,\"event\":\"%s\",\"state\":\"%s\",\"source\":\"%s\",\"distance_cm\":%.0f}",
    millis() / 1000, name, STATES[stateIdx], source, distanceCm);
  queueJson(TxKind::Event, buf);
}

void publishStatus() {
  const char* dest = stateIdx >= 2 ? "A06" : "";
  const char* station = stateIdx >= 3 ? (stateIdx >= 5 ? "A06" : "A01") : "";
  char buf[256];
  snprintf(buf, sizeof(buf),
    "{\"device_id\":\"unit-01\",\"uptime_s\":%lu,\"state\":\"%s\",\"distance_cm\":%.0f,\"tilt_deg\":%d,"
    "\"edge\":%d,\"train_near\":%d,\"help\":0,\"station\":\"%s\",\"dest\":\"%s\"}",
    millis() / 1000, STATES[stateIdx], distanceCm, 20 + (int)(millis() / 1000 % 7),
    edge, stateIdx == 3 ? 1 : 0, station, dest);
  queueJson(TxKind::Status, buf);
}

// ---------------------------------------------------------------- main loop (stands in for sensors)

unsigned long lastSensor = 0, lastStatus = 0, lastState = 0, lastReport = 0, lastLoopStart = 0;
unsigned long loopMaxMs = 0;

void setup() {
  Serial.begin(115200);
  Serial.println("FAHHH? MQTT connectivity test (not the team firmware)");
  startMqttTask();
  lastLoopStart = millis();
}

void loop() {
  // How long since the previous loop() started? If the network ever blocked
  // this loop, this number would jump to seconds.
  unsigned long now = millis();
  unsigned long gap = now - lastLoopStart;
  lastLoopStart = now;
  if (gap > loopMaxMs) loopMaxMs = gap;

  if (now - lastSensor >= 120) {           // same rate as the HC-SR04 in C2
    lastSensor = now;
    distanceCm += (float)random(-3, 4);
    distanceCm = constrain(distanceCm, 85.0f, 115.0f);
  }
  if (now - lastState >= 10000) {          // walk through the journey every 10 s
    lastState = now;
    stateIdx = (stateIdx + 1) % 7;
    publishEvent(STATES[stateIdx], "connectivity_test");
    if (stateIdx == 2) { edge = true; distanceCm = 135; publishEvent("EDGE_WARNING", "connectivity_test"); }
    if (stateIdx == 3 && edge) { edge = false; distanceCm = 100; publishEvent("EDGE_CLEAR", "connectivity_test"); }
  }
  if (now - lastStatus >= 2000) {          // C3 heartbeat
    lastStatus = now;
    publishStatus();
  }
  if (now - lastReport >= 5000) {
    lastReport = now;
    Serial.printf("[TEST] wifi=%s mqtt=%s lastConnectMs=%lu attempts=%lu published=%lu failed=%lu dropped=%lu loopMaxMs=%lu\n",
                  WiFi.status() == WL_CONNECTED ? "up" : "down", mqttReady.load() ? "up" : "down",
                  (unsigned long)lastConnectMs.load(), (unsigned long)connectAttempts.load(),
                  (unsigned long)published.load(), (unsigned long)publishFailed.load(),
                  (unsigned long)dropped.load(), loopMaxMs);
    loopMaxMs = 0;                         // max per 5 s window
  }
  delay(1);
}
