# Connectivity test: ESP32 in Wokwi → HiveMQ public broker → dashboard

| | |
|---|---|
| **Date** | Tue 27 Oct 2026, about 22:00–22:18 WIB |
| **Run by** | Stanley |
| **What** | `tests/connectivity/sketch.ino` (test sketch, not the team firmware): ESP32 only, C3 task-based MQTT pattern, publishes C3 v3 payloads with made-up values |
| **Broker** | `broker.hivemq.com:8883`, TLS (`setInsecure()`), no login |
| **Dashboard** | `dashboard/dashboard.py` on Stanley's Mac |
| **Evidence** | Wokwi Serial log (below), dashboard CSV log `2026-10-27_wokwi-connectivity_dashboard-log.csv` |

## Results

| Check | Result | Status |
|---|---|---|
| Wokwi Wi-Fi joins `Wokwi-GUEST` | `[NET] Wi-Fi connected, IP 10.10.0.2` within the first [TEST] line | Pass |
| TLS + MQTT connect to the public broker | Connected on the first attempt in **7275 ms**; reconnect later took **5964 ms** (Wokwi simulated time) | Pass |
| `loop()` not held up by the network (C3 claim) | `loopMaxMs` stayed **1–3 ms** in every 5 s window, including both 6–7 s connects. 14 ms once, in the boot window | Pass (for this test sketch) |
| Status heartbeat reaches the dashboard | While the simulation ran normally, 46 of 49 gaps between received statuses were exactly **2.0 s** | Pass |
| Last Will → dashboard offline, then recovery | Broker published `online=0` at 22:15:30; cane reconnected; `online=1` at 22:16:41; dashboard went Offline then Online | Pass |
| Messages while offline | 1 event (`ON_TRAIN`, uptime 40 s) never arrived: it fell in the disconnected window and was dropped, as C3 describes (QoS 0, no offline backlog) | As designed |
| Wi-Fi in the first version of the test sketch | **Failed** (`wifi=down` for 90 s): the task called `WiFi.reconnect()` immediately after `WiFi.begin()` and every 5 s, restarting the join before it could finish. Fixed by giving each attempt 15 s. **The same bug is in the C3 reference code** | Bug found, fixed in test sketch |

## Observation: Wokwi simulation slowed down

Two pauses in the dashboard log: 20 s and 95 s of real time passed while the ESP32's `uptime_s` advanced only 2 s and 8 s. Over the whole run: 210 s real time, 104 s simulated time (about half speed). The dashboard and broker delivered every message on time; the simulation itself slowed, most likely because the Wokwi browser tab was in the background while the dashboard was in front.

The stall also caused the one disconnect: the ESP32 could not send its MQTT keep-alive ping in time (PubSubClient default 15 s; broker allows 1.5×), so the broker dropped it and sent the Last Will.

**For tests and the demo video:** keep Wokwi and the dashboard in two windows side by side, not two tabs. **Suggested firmware change:** `mqtt.setKeepAlive(30)`, so a short simulation stall does not cause a disconnect (the dashboard still flags a silent cane after 6 s via the stale-status check).

## Wokwi Serial log (second run, after the Wi-Fi fix)

```
FAHHH? MQTT connectivity test (not the team firmware)
[NET] Wi-Fi connected, IP 10.10.0.2
[NET] connecting to broker.hivemq.com:8883 (TLS)...
[TEST] wifi=up mqtt=down lastConnectMs=0 attempts=1 published=0 failed=0 dropped=2 loopMaxMs=14
[TEST] wifi=up mqtt=down lastConnectMs=0 attempts=1 published=0 failed=0 dropped=6 loopMaxMs=1
[NET] MQTT connected in 7275 ms
[TEST] wifi=up mqtt=up lastConnectMs=7275 attempts=1 published=2 failed=0 dropped=6 loopMaxMs=2
[TEST] wifi=up mqtt=up lastConnectMs=7275 attempts=1 published=4 failed=0 dropped=6 loopMaxMs=1
[TEST] wifi=up mqtt=up lastConnectMs=7275 attempts=1 published=9 failed=0 dropped=6 loopMaxMs=3
[TEST] wifi=up mqtt=up lastConnectMs=7275 attempts=1 published=11 failed=0 dropped=6 loopMaxMs=1
[TEST] wifi=up mqtt=up lastConnectMs=7275 attempts=1 published=16 failed=0 dropped=6 loopMaxMs=3
[NET] connecting to broker.hivemq.com:8883 (TLS)...
[TEST] wifi=up mqtt=down lastConnectMs=7275 attempts=2 published=18 failed=0 dropped=8 loopMaxMs=2
[NET] MQTT connected in 5964 ms
[TEST] wifi=up mqtt=up lastConnectMs=5964 attempts=2 published=18 failed=0 dropped=10 loopMaxMs=2
[TEST] wifi=up mqtt=up lastConnectMs=5964 attempts=2 published=20 failed=0 dropped=10 loopMaxMs=2
[TEST] wifi=up mqtt=up lastConnectMs=5964 attempts=2 published=24 failed=0 dropped=10 loopMaxMs=2
[TEST] wifi=up mqtt=up lastConnectMs=5964 attempts=2 published=26 failed=0 dropped=10 loopMaxMs=2
[TEST] wifi=up mqtt=up lastConnectMs=5964 attempts=2 published=30 failed=0 dropped=10 loopMaxMs=3
```

## What this does and does not prove

- Proves: Wokwi → public broker over TLS works; the task pattern keeps `loop()` free in this sketch; payloads match what the dashboard expects; offline detection works end to end.
- Does not prove: the same numbers inside the full firmware (more work in `loop()`, real sensors). Test T7 must still be run with William's firmware.
- Timings are Wokwi simulated time, not real hardware.
