# Connectivity test sketch

Owner: Stanley. **Not the team firmware.** A minimal ESP32-only Wokwi project that checks the MQTT path before the real firmware has MQTT:

- Wokwi Wi-Fi → `broker.hivemq.com:8883` over TLS
- the C3 task-based MQTT pattern (network in a FreeRTOS task, `loop()` never waits)
- the dashboard receives C3 v3 payloads (made-up values, `device_id` unit-01)

It prints `[TEST] … loopMaxMs=…` every 5 s: the longest gap between two `loop()` runs. If the network ever blocked the loop, that number would jump to seconds.

## Run it

1. wokwi.com → New Project → ESP32. Paste `sketch.ino` and `diagram.json`.
2. Library Manager → **+** → `PubSubClient` (this creates `libraries.txt`).
3. Start the dashboard (`python dashboard.py`), then press Play in Wokwi.
4. Keep Wokwi and the dashboard in **two windows side by side**; a background tab slows the simulation down.

Set `#define USE_TLS 0` to test plain port 1883 instead.

Do not run it at the same time as the real firmware: both report as unit-01 (different client IDs, so they don't kick each other off, but the dashboard would mix their data).

Results of the first run: `tests/results/2026-10-27_wokwi-connectivity.md`.
