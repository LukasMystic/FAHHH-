# Firmware tests: ESP32 in Wokwi → HiveMQ public broker → dashboard

| | |
|---|---|
| **Date** | Fri 30 Oct 2026, from 11:02 WIB |
| **Run by** | Stanley |
| **Firmware** | `firmware/sketch.ino` on `main` (PR #12), Wokwi project https://wokwi.com/projects/478926704931540993 |
| **Contract** | C3 v4 (PR #13) |
| **Broker** | `broker.hivemq.com:8883`, TLS (`setInsecure()`), no login |
| **Dashboard** | `dashboard/dashboard.py --name stanley-test` on Stanley's Mac |
| **Evidence** | Serial logs `2026-10-30_firmware-block{A,BC,D,E-t7b}_serial.txt`, dashboard CSV `2026-10-30_firmware-dashboard-log.csv` (Blocks A–D), 26 screenshots in `assets/screenshots/R4_test_*.png` (list at the end). Sounds (beeps, LED patterns) were checked by ear and eye by Stanley; no log records them |

Test steps and expected results: `tests/test_scenarios.md`. Wokwi cards used: Blue = A_MASUK, Green = A_P1_WAIT, Yellow = A_P2_WAIT, Red = TRAIN_INSIDE, NFC Tag (gray) = B_P1_PERON, Key Fob = B_LUAR.

## Block A: one full journey (T1, T10, T11, T2)

Route FLAT/FLAT, platforms P1/P1, destination `DEMO_B` (set with `SIM DEST B`), HC-SR04 at 21 cm, MPU6050 upright. Times are the firmware's `millis()` from the Serial `EVENT t=…` lines.

| Test | What was done | What happened (Serial) | Dashboard | Status |
|---|---|---|---|---|
| **T1** Route to the platform | `SIM DEST B`, knob press, Blue card, `SIM TAG A_SIMPANG`, (T10), Green card | `ROUTE destination=DEMO_B … next=A_MASUK` (69.3 s); `CHECKPOINT A_MASUK source=RFID_PHYSICAL` (102.5 s); `CHECKPOINT A_SIMPANG source=SERIAL_SIMULATION` (144.7 s); `CHECKPOINT A_P1_WAIT`, `STATE SEEK_PLATFORM -> WAIT_TRAIN`, `WAIT_TRAIN at A_P1_WAIT; expected train=TRAIN01 side=P1 dest=DEMO_B` (185.8 s) | Status `dest` `DEMO_B` from 70 s, `station` `DEMO_A` from 104 s, state `WAIT_TRAIN` from 186 s | Pass |
| **T10** Wrong platform | Yellow card (A_P2_WAIT) while the route expects P1, then Green | `CHECKPOINT_REJECTED got=A_P2_WAIT expected=A_P1_WAIT state=SEEK_PLATFORM` (170.5 s); state unchanged; Green accepted 15 s later | `CHECKPOINT_REJECTED` event received | Pass (5 short low beeps heard) |
| **T11** Boarding too early, wrong train | Potentiometer to ADC 2746; (a) Red card; (b) `SIM TRAIN TRAIN01 P2 B`; (c) `SIM TRAIN TRAIN01 P1 B`, `SIM STOPPED`, `SIM DOOR OPEN P1`, Red card | `SIM_TRAIN_NEAR` (218.2 s). (a) `CHECKPOINT_REJECTED got=TRAIN_INSIDE` (257.2 s), still `WAIT_TRAIN`. (b) `TRAIN_REJECTED got=TRAIN01/P2/B expected=TRAIN01/P1/B` (287.4 s), no `BOARDING_READY`. (c) `TRAIN_MATCH`, `TRAIN_STOPPED`, `TRAIN_DOOR_OPEN`, `BOARDING_READY` (526.1 s), then `STATE WAIT_TRAIN -> ON_TRAIN`, `BOARDING_CONFIRMED_BY_TAG` (539.9 s) | `train_near` 1 from 220 s, 0 after boarding; all events received | Pass (5 short beeps on the early door tag, no beep on the wrong train, 3 beeps on ready, 2 on boarding: heard) |
| **T2** Arrive, step off, exit | `SIM ARRIVE B`, `SIM STOPPED`, `SIM DOOR OPEN P1`, NFC Tag, `SIM TAG B_SIMPANG`, Key Fob | `STATE ON_TRAIN -> ARRIVING` (562.1 s); `DESTINATION_PLATFORM_CONFIRMED B_P1_PERON` from the physical NFC tag (605.2 s); `CHECKPOINT B_SIMPANG` (651.9 s); `CHECKPOINT B_LUAR`, `STATE ARRIVING -> COMPLETE` (665.7 s) | `station` `DEMO_B` from 606 s; state `COMPLETE` from 666 s | Pass |

Operator notes: four `Unknown command; type HELP` lines between 310 s and 505 s are answer lines typed by mistake; `SIM TRAIN TRAIN01 P1 B` was then entered a second time (second `TRAIN_MATCH` at 505.2 s). Neither changed the journey.

### MQTT during Block A

| Check | Result |
|---|---|
| Connect | `MQTT connected; QoS 0 publishes enabled` before the third Serial status block; first status at the dashboard at uptime 12 s. 5 messages dropped before that (C3: no offline backlog) |
| Events | **24 of 24** events in Serial arrived at the dashboard, in order |
| Status heartbeat | 335 status messages from uptime 12 s to 680 s, **every gap exactly 2 s**: none lost |
| Disconnects | None: `MQTT: connected` in all 148 Serial status blocks after the connect |
| C3 v4 fields | `dest`, `station`, `state` and `train_near` changed exactly as C3 v4 describes (see T1, T11, T2) |
| Simulation speed | 668 s of ESP32 time in 764 s of real time (about 87%) |

## Blocks B and C: unregistered tag, sensors, SOS (T9, T3, T4, T6, T5)

New simulation run (boot, then `MQTT connected`), destination `DEMO_B`, knob pressed once (`SEEK_PLATFORM` at 24.6 s). Evidence: `2026-10-30_firmware-blockBC_serial.txt`; the dashboard CSV is the same file as Block A.

| Test | What was done | What happened (Serial) | Dashboard | Status |
|---|---|---|---|---|
| **T9** Unregistered tag | `SIM TAG XYZ` in `SEEK_PLATFORM` (all six Wokwi cards are registered, so no physical unknown card exists) | `CHECKPOINT_REJECTED got=XYZ expected=A_MASUK state=SEEK_PLATFORM` (36.2 s), source `SERIAL_SIMULATION`; state unchanged | Event received | Pass (5 short low beeps heard) |
| **T3** Edge | HC-SR04 21 cm → about 85 cm → back | `EDGE_WARNING` source `HC_SR04_MPU6050` at 84.7 cm (162.5 s); `Tepi: PERINGATAN` in the status while active; `EDGE_CLEAR` at 29.1 cm (182.3 s) | Both events received; `edge` = 1 while active | Pass (long high beep heard) |
| **T4** Cane tilted | MPU6050 accel set so the tilt reads 73°, then HC-SR04 21 → about 87 cm → back | Tilt 45° then 73° in the status; `CANE_TILT_ADVISORY` (221.2 s); `EDGE_WARNING` source **`HC_SR04_RAW_FALLBACK`** at 86.7 cm (273.5 s); `EDGE_CLEAR` (287.3 s). Edge detection kept working on the raw distance | Events received; tilt above 65° in the status | Pass |
| **T6** Short SOS press | SOS pressed for less than 3 s | No `HELP_REQUEST` and no state change between 287.3 s and 338.2 s | No change | Pass (short press done in this window, confirmed by Stanley) |
| **T5** SOS, then an edge | SOS held; then HC-SR04 21 → about 47 cm → back; then `ACK HELP` | `STATE SEEK_PLATFORM -> EMERGENCY`, `HELP_REQUEST` (338.2 s); `Bantuan: permintaan lokal aktif` in every status block while active; `EDGE_WARNING` **during EMERGENCY** at 47.4 cm (359.8 s), `EDGE_CLEAR` (370.4 s); `ACK HELP` → `STATE EMERGENCY -> SELECT_DEST` and `HELP ACK is demo reset only; not proof assistance arrived` (379.7 s) | `EMERGENCY` and `HELP_REQUEST` received; edge events during the emergency received | Pass (4 help beeps, then the edge beep cutting in: heard) |

MQTT during Blocks B and C: **12 of 12** events arrived at the dashboard; `MQTT: connected` in every status block after the first one at boot.

Incidental observation between the two runs: the last status of Block A arrived at 11:19:10 and the broker's Last Will (`online=0`) at 11:19:55, **45 s later** (1.5 × keep-alive 30 s). After the restart, the first status arrived at uptime 8 s. T7a repeats this on purpose with recorded times.

### `loopMaxMs` (input for T7b)

The firmware prints the longest `loop()` iteration of the last 5 s. MQTT was connected for every value below, so none of the differences come from the network.

| Condition (HC-SR04 about 21 cm unless noted) | Status blocks | `loopMaxMs` median (min–max) |
|---|---|---|
| `SELECT_DEST`, cane upright | 82 (A: 7, B/C: 75) | **13.5** (12.9–25.3) |
| `COMPLETE` | 17 | 13.4 (12.9–31.7) |
| `SEEK_PLATFORM` | 24 in A, 42 in B/C | 23.6 in A, 13.8 in B/C |
| `SEEK_PLATFORM`, tilt above 65° (raw fallback) | 17 | 24.1 (13.9–24.3) |
| `EMERGENCY` | 8 | 24.0 (23.7–27.4) |
| `ARRIVING` | 21 | 25.4 (24.5–28.0) |
| `WAIT_TRAIN` | 70 | 35.6 (35.0–36.6) |
| `SELECT_DEST` at the Wokwi default 403 cm | 6 | 31.2 (25.3–39.3) |

The measured iteration includes the one that prints the 5 s Serial status block, and the larger values occur with longer blocks (`WAIT_TRAIN` adds a `Train:` line, `EMERGENCY` a `Bantuan:` line, raw fallback longer texts). At 403 cm the echo itself takes about 24 ms. `SEEK_PLATFORM` differed between the two runs (23.6 vs 13.8 ms) for a reason not identified. **T7b therefore compares one fixed condition: `SELECT_DEST`, 21 cm, cane upright, 13.5 ms median with the broker connected.**

## Block D: T7a, cane disconnects and comes back

Evidence: `2026-10-30_firmware-blockD_serial.txt` (33 status blocks, about 165 s) and the dashboard CSV.

**Planned stop and restart (end of Block A → start of Block B):**

| Check | Result | Status |
|---|---|---|
| Offline after the simulation stopped | Last status 11:19:10 (uptime 886 s); broker's Last Will `online=0` at 11:19:55, **45 s later** = 1.5 × keep-alive 30 s | Pass |
| Back online after Play | `online=1` at 11:25:32, first status at uptime **8 s** | Pass |
| Dashboard after the cane went silent | First **No Data** (gray), "Updated 13 s ago", last known values kept (`R4_test_07a_2`, simulation stopped, before the Last Will); later **Offline** with "Updated 296 s ago" (`R4_test_07b_1`) | Pass |

**Unplanned drop during the Block D run** (this is what the Block D log shows, not a Stop):

| Time | Cane (Serial) | Broker and dashboard |
|---|---|---|
| uptime 8–114 s | `MQTT: connected` | Status every 2 s (13:58:21 → 14:00:26) |
| uptime 116 – about 155 s | Still `MQTT: connected`, drop counter unchanged (3): the cane believes its publishes succeed | **Nothing arrives**: about 20 status messages lost |
| 14:01:11 | | Last Will `online=0`, **45 s after the last status** |
| about 160 s | `MQTT: offline; drop=4`, then `drop=7`: the cane noticed the lost connection and drops messages instead of queuing them | |

So the connection broke silently (a half-open TCP connection, most likely in the Wokwi public gateway, which its docs describe as "medium stability"). With QoS 0 the cane cannot tell which publishes were lost; it noticed about 45 s later through the MQTT keep-alive. The dashboard's 6 s stale check and the broker's Last Will are what tell the companion. `loopMaxMs` stayed 13.8 ms (median of 30 connected blocks) and 13.8 ms in the two offline blocks: the sensor loop was not affected.

One more stop did not follow the 45 s pattern: after Block C the last status arrived at 11:41:09 but `online=0` only at 11:43:54 (165 s), probably because the simulation was paused or slowed in a background tab rather than stopped. The dashboard's stale check still showed the cane as not live after 6 s.

## Block E: T7b, broker unreachable, alarm stays local

A copy of the Wokwi project with `constexpr char MQTT_HOST[]="10.255.255.1";` (an address that never answers), team project stopped. Evidence: `2026-10-30_firmware-blockE-t7b_serial.txt`.

| Check | Result | Status |
|---|---|---|
| MQTT | `MQTT: offline` in all 11 status blocks (57 s); the drop counter rose 2 → 29: messages are dropped, not queued (C3) | As designed |
| Edge alert without the broker | HC-SR04 moved from 13 to about 175 cm: `EDGE_WARNING` (18.2 s, source `HC_SR04_MPU6050`), `Tepi: PERINGATAN` in the status, `EDGE_CLEAR` at 19.1 cm (20.6 s) | Pass (long beep heard right away) |
| `loopMaxMs`, `SELECT_DEST`, 22 cm, upright | **13.64 ms median** (7 blocks after the edge, 13.14–14.17); 13.4–17.0 in the first four blocks (boot and edge) | Pass |
| Compared with the broker connected | **13.5 ms median** in the same condition (82 blocks, Blocks A–C); 13.8 ms in Block D (30 blocks) | No measurable difference |

Limits: the firmware prints neither the Wi-Fi state nor each MQTT connect attempt, so this log cannot show how long each attempt to `10.255.255.1` lasted. In the connectivity test (Tue 27 Oct) Wokwi-GUEST joined within seconds, so the network task was most likely retrying the connect the whole time. The claim for the report is therefore: with the broker unreachable, the edge alert still fired and `loop()` stayed at the same 13–14 ms as with the broker connected.

## Block F: T8, bad messages

| Test | Result | Status |
|---|---|---|
| T8 `hello` and `{"device_id":"other"}` on `device/status`, from the HiveMQ WebSocket Client, with the team cane online | The dashboard kept running and showed no data from either message; the footer counter read **"Ignored 4 message(s)"** after the test (0 at 11:05). Both test messages were published twice (confirmed by Stanley), so 4 of 4 bad messages were ignored. Serial: `MQTT: connected` throughout, the cane was not affected | Pass |

## What this does and does not prove

- Proves: the full journey runs as C2/C3 v4 describe on the wired Wokwi circuit; wrong platform, early door tag, wrong train and unknown tags are rejected; edge, tilt and SOS behave as C2 describes, including an edge during an emergency; every event (36 of 36) and every status (898 in three runs, each 2 s after the previous one) reached the dashboard over the public broker; the Last Will marks the cane offline 45 s after it stops or its connection silently breaks; with the broker unreachable, the edge alert still fires and `loop()` timing does not change.
- Shows a limit: when the connection breaks silently, QoS 0 messages are lost for up to about 45 s and the cane does not know (Block D: about 20 status messages). The current state comes back with the first status after reconnecting; safety alerts are unaffected because they are local.
- Does not prove: train identity, stop and door state (typed in Serial), beacon distance (potentiometer) or the junction checkpoints (`SIM TAG`): these are simulations. Sounds were confirmed by ear, not by a log. Timings are Wokwi simulated time.

## Screenshots

Full-screen captures (Wokwi with Serial on the left, dashboard on the right), in `assets/screenshots/`:

| Test | Files |
|---|---|
| T1 | `R4_test_01a_route-checkpoints`, `R4_test_01b_waiting-for-train` |
| T2 | `R4_test_02a_arriving`, `R4_test_02b_doors-open-destination`, `R4_test_02c_stepped-off`, `R4_test_02d_arrived-events`, `R4_test_02e_journey-done` |
| T3 | `R4_test_03a_edge-ahead`, `R4_test_03b_edge-cleared` |
| T4 | `R4_test_04_cane-tilted` |
| T5 | `R4_test_05a_emergency`, `R4_test_05b_ack-help-reset` |
| T7a | `R4_test_07a_1_online-after-play`, `R4_test_07a_2_no-data` (Offline: see `R4_test_07b_1`) |
| T7b | `R4_test_07b_1_broker-unreachable`, `R4_test_07b_2_still-offline` |
| T8 | `R4_test_08a_websocket-publish`, `R4_test_08b_ignored-messages` |
| T9 | `R4_test_09_unknown-tag-rejected` |
| T10 | `R4_test_10_wrong-platform-rejected` |
| T11 | `R4_test_11a_train-door-nearby`, `R4_test_11b_door-tag-too-early`, `R4_test_11c_wrong-train`, `R4_test_11d_right-train-stopped`, `R4_test_11e_ready-to-board`, `R4_test_11f_boarded` |

T6 (nothing happens) has no screenshot; the Serial log is the evidence.
