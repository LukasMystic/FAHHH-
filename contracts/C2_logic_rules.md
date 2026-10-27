# C2 · Logic rules

| | |
|---|---|
| **Owner** | William |
| **Used by** | Kezia, Stanley |
| **Due** | Mon 26 Oct, 18:00 |
| **Status** | DRAFT, pending approval from all four members |

Only William edits this file. Once C2 is published as a final contract, any change requires `CONTRACT CHANGE C2` and 👍 from all four members.

These rules describe William's firmware draft. They must be checked against `firmware/sketch.ino` in the separate firmware PR. The draft passed a local syntax check but has not been retested in Wokwi. C3 v3 uses the same event names as Serial. The MQTT events below are planned; the ESP32 has not published them in a verified Wokwi test yet.

## States

| State | Feature | Condition / threshold | Output (pattern) | MQTT event (planned) |
|---|---|---|---|---|
| `SELECT_LINE` | P2 | At startup or after reset, rotate the encoder to choose Demo A/B; short press to continue | Serial `MENU line`; one short beep when the selection changes | `SELECT_LINE` on a state transition; rotary menu changes remain Serial only |
| `SELECT_DEST` | P2 | Rotate the encoder to choose a station on the demo line; short press to confirm the destination | Serial `MENU destination`; one short beep when the selection changes | `SELECT_DEST` on a state transition; rotary menu changes remain Serial only |
| `SEEK_PLATFORM` | P2 | Destination confirmed; wait for a registered RFID tag or `SIM TAG <ID>` | Serial `ROUTE`, then `RFID_CHECKPOINT` and `CHECKPOINT` when a tag is read | `SEEK_PLATFORM` on transition; `CHECKPOINT` when a tag is read. A tag does not verify arrival at the platform |
| `WAIT_TRAIN` | P2/P1 | A registered RFID tag other than the destination is read. Simulated beacon becomes near at ADC >2600 and far at ADC ≤2100. User presses the encoder after confirming boarding | Two short beeps on entry; `SIM_TRAIN_NEAR` and three short beeps when near; `BOARDING_CONFIRMED_BY_USER` after confirmation | `WAIT_TRAIN`, `SIM_TRAIN_NEAR`, `BOARDING_CONFIRMED_BY_USER`; no measured `BOARDING_GAP` |
| `ON_TRAIN` | P1 | Boarding confirmed from `WAIT_TRAIN`; matching `SIM ARRIVE <ID>` or a destination tag in the demo triggers the next state | Two medium beeps on boarding; Serial labels the arrival source as simulated | `ON_TRAIN`; `SIM_DESTINATION_APPROACH` only for simulated arrival |
| `ARRIVING` | P1 | Simulated arrival matches the destination; user presses the encoder after confirming alighting | `SIM_DESTINATION_APPROACH` when triggered by `SIM ARRIVE`; three medium beeps; then `ALIGHTING_CONFIRMED_BY_USER` | `ARRIVING`; `ALIGHTING_CONFIRMED_BY_USER` after user confirmation |
| `COMPLETE` | P1/P2 | Alighting confirmed, or a destination tag is read in `SEEK_PLATFORM` in the demo | Three short beeps; final state in Serial | `COMPLETE` on transition |
| Any state, without changing the travel state | S1/P3 | HC-SR04: distance > baseline +15 cm and >25 cm for three consecutive readings, sampled every 120 ms. Clear after 700 ms of valid non-jump readings. Use `distance × cos(MPU angle)` when the angle is ≤65°; otherwise use raw distance and a separate raw baseline | `EDGE_WARNING`: one long high beep; `EDGE_CLEAR` when safe. Missing echo triggers `EDGE_SENSOR_FAULT`; MPU failure triggers `MPU_FAULT_RAW_FALLBACK`. Either fault gives two long low beeps. A sensor failure does not silently clear an active edge warning | `EDGE_WARNING`, `EDGE_CLEAR`, `EDGE_SENSOR_FAULT`, `MPU_FAULT_RAW_FALLBACK`, `CANE_TILT_ADVISORY` |
| `EMERGENCY` | S2/P3 | Help button remains LOW for 40 ms debounce, then is held for 3 seconds from any state; latched until demo-only `ACK HELP` | `HELP_REQUEST`, four high-pitched beeps; local help status remains active without Wi-Fi | `HELP_REQUEST` and the `EMERGENCY` state transition event; this does not prove that help was received |
| No state/rule yet | P1 | Train-platform gap or step measurement is not implemented | No gap safety claim | `BOARDING_GAP` must not be sent as a real measurement |
| No state/rule yet | Battery | No battery voltage sensor or reading | None | `LOW_BATTERY` must not be sent |

Main transitions: `SELECT_LINE` → `SELECT_DEST` → `SEEK_PLATFORM` → `WAIT_TRAIN` → `ON_TRAIN` → `ARRIVING` → `COMPLETE`. In the demo, a destination tag in `SEEK_PLATFORM` can go directly to `COMPLETE`. The help button moves any state to `EMERGENCY`. Holding the encoder for more than 1.2 seconds resets the menu when help is not active. Serial `ACK HELP` resets the demo only.

## Alert language

| Pattern | Meaning |
|---|---|
| One short beep, 650 Hz, 45 ms | Rotary selection changed; ordinary navigation feedback |
| Two short beeps, 700 Hz, 100 ms | RFID checkpoint recognized and state changed to `WAIT_TRAIN` |
| Three short beeps, 900 Hz, 100 ms | **Simulated** beacon indicates a nearby train; the user must still verify its line and direction |
| One long high beep, 1200 Hz, 700 ms | Edge hazard: `EDGE_WARNING` |
| Two long low beeps, 500 Hz, 500 ms each | Sensor fault: `EDGE_SENSOR_FAULT` or `MPU_FAULT_RAW_FALLBACK`; distance information may be degraded or unavailable |
| Two beeps, 750 Hz, 220 ms | Cane angle >65° for 2 seconds; `CANE_TILT_ADVISORY` |
| Four beeps, 1600 Hz, 250 ms | Local help request active; `HELP_REQUEST` |

Priority: an edge hazard or sensor fault can interrupt the help pattern, which resumes afterward. If both are pending, the fault pattern plays first, then the edge pattern, then help resumes. Ordinary navigation cues do not override hazard, fault, or help cues. The Wokwi LED stands in for vibration output; the demo has no vibration motor or spoken station names.

**P3 rule:** S1 safety alerts are decided on the ESP32 and never wait for Wi-Fi/MQTT. The same rule must apply to P1 once gap measurement is implemented. The S2 help button also produces a local cue without a connection. MQTT publishing under C3 v3 remains pending firmware integration and Wokwi testing; local safety alerts never wait for it.

**Simulation labels:** the potentiometer stands in for BLE RSSI; `SIM ARRIVE` stands in for train telemetry; and `SIM TAG` stands in for an RFID read through Serial. A physical RFID read only proves that a registered tag was seen. It does not verify the platform or train. Station names are currently shown only in Serial, so the menu is not yet independently usable by a blind passenger.