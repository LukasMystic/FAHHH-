# C2 · Logic rules

| | |
|---|---|
| **Owner** | William |
| **Used by** | Kezia, Stanley |
| **Due** | Mon 26 Oct, 18:00 |
| **Status** | DRAFT — owner to fill |

Only the owner edits this file. Changes after publishing: `CONTRACT CHANGE C2` + 👍 from all four.

## States

| State | Feature | Condition / threshold | Output (pattern) | MQTT event |
|---|---|---|---|---|
| | P1 | | | `BOARDING_GAP` |
| | P2 | | | `GUIDE_STEP` / `ARRIVED_PLATFORM` |
| | S1 | | | `LEVEL_CHANGE` |
| | S2 | | | `EMERGENCY` |
| | — | | | `LOW_BATTERY` |

## Alert language

| Pattern | Meaning |
|---|---|
| | |

Rule: safety alerts (P1, S1) are decided on the ESP32 and never wait for Wi-Fi/MQTT (P3).
