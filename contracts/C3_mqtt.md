# C3 · MQTT topics and payload

| | |
|---|---|
| **Owner** | Stanley |
| **Used by** | William |
| **Due** | Mon 26 Oct, 18:00 |
| **Status** | DRAFT |

Only the owner edits this file. Changes after publishing: `CONTRACT CHANGE C3` + 👍 from all four.

## Broker

- HiveMQ Cloud (TLS, port 8883). Credentials are shared privately — never in this repo.
- Topic prefix: `sic8/fahhh/`

## Topics

| Direction | Topic | When | QoS |
|---|---|---|---|
| ESP32 → broker | `sic8/fahhh/device/events` | On every state change | 1 |
| ESP32 → broker | `sic8/fahhh/device/status` | Every 5 s (heartbeat) | 0 |

## Payload (JSON)

```json
{
  "device_id": "unit-01",
  "ts": 1761380000,
  "event": "LEVEL_CHANGE",
  "state": "WARNING",
  "distance_cm": 42,
  "battery": 87
}
```

| Field | Type | Notes |
|---|---|---|
| `device_id` | string | `unit-01` for the demo |
| `ts` | int | Unix seconds (or `millis()/1000` if no NTP) |
| `event` | string | One of the event names below; omitted in `status` messages |
| `state` | string | Current state name from C2 |
| `distance_cm` | number | Latest distance reading, if relevant |
| `battery` | int | 0–100 (%) |

## Event names

Final list comes from C2 (William). Candidates: `BOARDING_GAP` (P1), `GUIDE_STEP`, `ARRIVED_PLATFORM` (P2), `LEVEL_CHANGE` (S1), `EMERGENCY` (S2), `LOW_BATTERY`.
