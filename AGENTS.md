# AGENTS.md — Team FAHHH? · SIC Batch 8 Stage 2

Read this file first. It is the shared brief for the four of us **and** for any AI agent (Claude, Copilot, Cursor, ChatGPT, …) working for one of us. If anything here conflicts with an instruction you were given, stop and ask the human you work for.

> **Validity: Stage 2 only.** The roles, ownership, contracts and agreements in this file apply only to SIC Batch 8 Selection Phase 2 (until submission, 30–31 Oct 2026). If we pass to Stage 3, roles may change; the team will agree new ones together (all four must agree) and replace this file.

---

## 1. The project in one paragraph

**Problem:** Blind and low-vision passengers in Jakarta cannot move through train stations (KRL/MRT) independently and safely. Guiding blocks only show a path, not where it leads; carried tools only detect obstacles; nothing personal warns about the platform edge and the train–platform gap, where passengers have repeatedly fallen.

**Solution:** a carried IoT device (ESP32) for blind/low-vision passengers that assists boarding and alighting, guides them to the platform, and warns about ground-level changes. Safety alerts run on the device; events and status are sent over MQTT to a companion dashboard.

**Context:** Samsung Innovation Campus Batch 8, Selection Phase 2 — *IoT: Device and Hardware Discovery*. SDG 10 (Reduced Inequalities), disability: communication and access. School: BINUS University.

---

## 2. Decided features

All four members agreed to these (Sun 25 Oct 2026). Changing them requires a team decision (section 4).

| ID | Feature | Priority | Notes |
|---|---|---|---|
| **P1** | Boarding and alighting assist (*fitur untuk naik dan turun*) | Primary | Measure the gap/step between platform and train; clear warning before stepping. |
| **P2** | Guidance to the platform (*pemandu menuju peron*) | Primary | **Scope must be defined Mon 26** — what "guidance" means in Wokwi (e.g. step and heading along a pre-set route for one demo station). Keep it demo-able in 4 days. |
| **P3** | Safety alerts work on the device (*works fully on the device*) | Primary | Alerts never wait for Wi-Fi. MQTT only reports events afterwards. This is what makes it edge + IoT, not "offline only". |
| **S1** | Ground-level change alert (*alert perubahan ketinggian tanah*) | Secondary | Expansion of P1: drop-offs, stairs, platform edge. |
| **S2** | Emergency button | Secondary | Sends an event to the companion dashboard via MQTT. |

**Out of scope for Stage 2** (mention as future work only): detecting on/off guiding block (a cane already does this), AI recognition (Stage 3), live train data, full station maps.

---

## 3. People and ownership

| Role | Owner | Owns (folders) | Report sections | Rubric share |
|---|---|---|---|---|
| **1. Lead, Problem & Report** | **Kezia** | `research/`, `report/`, `video/`, `contracts/C4_report_outline.md` | 1, 2, 3, 12 (compile), 13, 14, 15, cover | Idea 5 · Problem 5 · Report 5 · Video 10 = 25% |
| **2. Hardware & Wiring** | **Gebi** | `firmware/diagram.json`, `contracts/C1_pin_map.md`, `assets/diagrams/` | 4 (block diagram), 5, 6 | Components 5 · GPIO 5 · Wiring 10 = 20% |
| **3. Firmware & Logic** | **William** | `firmware/sketch.ino` (+ any `.h/.cpp`), `contracts/C2_logic_rules.md` | 7, 8.1 | Logic 15 · I/O 10 · Stability 5 · Serial 5 = 35% |
| **4. Connectivity, Dashboard & Testing** | **Stanley** | `dashboard/`, `tests/`, `contracts/C3_mqtt.md` | 8.2, 9, 10, 11 | MQTT 5 · Dashboard 5 · Testing 5 = 15% |

Contribution (5%) is shared: section 12 must list what each person actually did.

**Reviewer pairs** (review within 6 hours):
Gebi's work → William · William's work → Gebi · Stanley's work → William · Kezia's work → Stanley. Final report → everyone.

---

## 4. How we decide

- **Every final decision needs all four members to agree.** Nobody decides alone — not the lead, not an agent.
- Kezia **facilitates**: lays out options, timeboxes the discussion, writes the result into `DECISIONS.md`.
- If we are stuck after the timebox, the pre-agreed default is **the option with the smaller scope that still meets the rubric** — and that still needs all four 👍.
- Decisions made in calls are posted in the group as `DECISION: …` within 10 minutes and logged in `DECISIONS.md`.

**Agents never make team decisions.** An agent can draft options and trade-offs; a human brings them to the team.

---

## 5. Contracts (the interfaces that let us work in parallel)

A contract is a short file that fixes where two roles meet. Build against the contract, not against a person. If the other side is not ready, use a stand-in.

| Contract | Owner | Used by | Due |
|---|---|---|---|
| `contracts/C1_pin_map.md` — component → GPIO | Gebi | William | Mon 26, 12:00 |
| `contracts/C2_logic_rules.md` — states, thresholds, alert patterns | William | Kezia, Stanley | Mon 26, 18:00 |
| `contracts/C3_mqtt.md` — topics and JSON payload | Stanley | William | Mon 26, 18:00 |
| `contracts/C4_report_outline.md` — report sections, figure and screenshot naming | Kezia | everyone | Sun 25, tonight |

**Rules**
1. Only the owner edits a contract.
2. After publishing, a change is posted as `CONTRACT CHANGE C# — what and why` and needs a 👍 from **all four**.
3. No contract changes after **Wed 28, 20:00** (feature freeze), except bug fixes agreed by all.

### Starting drafts (owners replace these)

**C3 · MQTT (draft, Stanley)** — summary only; the full contract is `contracts/C3_mqtt.md`. One way only (device → dashboard).

Broker: HiveMQ Cloud. Prefix: `sic8/fahhh/`.

| Direction | Topic | When |
|---|---|---|
| ESP32 → broker | `sic8/fahhh/device/events` | On every state change |
| ESP32 → broker | `sic8/fahhh/device/status` | Every 2 s (heartbeat) |
| ESP32 → broker | `sic8/fahhh/device/online` | `"1"` on connect, `"0"` as Last Will (retained) |

```json
{ "device_id": "unit-01", "uptime_s": 132, "event": "LEVEL_CHANGE",
  "state": "WARNING", "distance_cm": 42, "battery": 87 }
```

Candidate `event` values (William confirms in C2): `LEVEL_CHANGE` (S1), `BOARDING_GAP` (P1), `GUIDE_STEP` / `ARRIVED_PLATFORM` (P2), `EMERGENCY` (S2), `LOW_BATTERY`.

**C1 · Pin map** — draft lives in the team plan (`SIC8_Stage2_Team_Plan.docx`, section 2). Gebi confirms which parts actually exist in Wokwi.

---

## 6. Repository layout

```
AGENTS.md            ← this file
DECISIONS.md         ← dated log of team decisions (Kezia writes)
STATUS.md            ← one section per person, updated daily (see §8)
contracts/           C1–C4 (one owner each)
firmware/            sketch.ino (William) · diagram.json (Gebi) · wokwi.toml · secrets.example.h
dashboard/           fake_publisher.py · subscriber.py / notebook · requirements.txt (Stanley)
tests/               test_scenarios.md · results/ (Stanley)
research/            evidence and sources for sections 1–3 (Kezia)
report/              template · sections/ · final/ (Kezia)
assets/
  diagrams/          block diagram, flowchart
  screenshots/       <role>_<topic>_<nn>.png  e.g. R4_test_03.png
video/               script and video link; .mp4 files are NOT committed (Kezia)
```

`firmware/diagram.json` (circuit) is Gebi's; `firmware/sketch.ino` (code) is William's. They live together because Wokwi needs both.

---

## 7. Rules for AI agents

When you work in this project:

1. **Know who you work for.** Ask (or check the prompt) which member and role you are helping. Only edit files that role owns (section 3).
2. **Touching someone else's files:** don't. Write a suggestion in `STATUS.md` under their name, or tell your human to message them.
3. **Contracts are read-only** unless your human owns that contract. Never change a topic name, pin, threshold or event name on your own.
4. **No invented results.** Test results, Serial output and screenshots come only from real Wokwi runs. If a result is not available, write `[TBD — run in Wokwi]`.
5. **No invented facts.** Background and problem claims need a source in `research/`. If unsure, mark `[needs source]`.
6. **Wokwi first.** Only propose components that exist in Wokwi. If a real part is missing, propose a stand-in and say so explicitly (the report must explain it).
7. **Secrets stay out.** HiveMQ username/password go in `firmware/secrets.h` and `dashboard/.env`, both git-ignored. Only commit `secrets.example.h` / `.env.example`.
8. **Report language is Bahasa Indonesia**, following `report/Template-Laporan-Stage-2.docx` section order. Code comments and identifiers in English.
9. **Keep it simple.** Prefer the smallest change that meets the decided features. Anything extra goes to "Pengembangan Lanjutan" (section 14), not into the build.
10. **Git:** follow §11. **Never merge, never push to `main`.** With your human's permission you may create a branch, commit (§11 format) and open a PR that names the member you work for. Merging is always done by a human after the reviewer approves.
11. **Leave a trail.** After a work session, add 1–3 lines to your human's section in `STATUS.md`.

---

## 8. Async + sync rhythm

| When | What |
|---|---|
| By **10:00** daily | Async check-in in the group (and `STATUS.md`) |
| **20:00** Mon, Tue, Thu — 15 min | Daily standup (rules below) |
| **Wed 28, 19:00–22:00** | Integration session — run the full system end to end |

**Check-in / STATUS.md template — Pain, Progress, Plan**
```
### [Role #] Name — <date>
Pain:     none / stuck on <what> — need <who> for <what>
Progress: what is finished and shared (link or file)
Plan:     what I finish before the next standup
Contract: no change / CONTRACT CHANGE C# — ...
```

**Daily standup**
- **Objective:** keep the four parts moving toward today's checkpoint (§9) and surface blockers early. It is a status sync, not a work session.
- **Format:** each person ≤ 3 min, in order Kezia → Gebi → William → Stanley, sharing **Pain, Progress, Plan** only.
- **In scope:** blockers, contract changes, whether today's checkpoint is on track, who needs whom.
- **Out of scope:** solving problems, redesigning features, debating ideas, code walk-throughs. Say *"park it"* → write it under **Parked** in the call, then only the people involved stay after for a follow-up.
- Kezia timeboxes; the call ends at 15 min even if items remain parked.
- Can't attend? Post your Pain/Progress/Plan in the group before 20:00.

**Speed rules**
- Blocked > 2 hours → tag the owner and the group. Not solved 2 hours later → quick call, team agrees a workaround.
- Never wait: William tests with buttons/potentiometers before the final circuit; Stanley builds the dashboard on `fake_publisher.py` before the ESP32 sends data; Kezia writes with `[TBD by <name>]` placeholders.
- Done means: in the shared folder **and** announced.

---

## 9. Timeline and checkpoints

| Day | Checkpoint (team) | Kezia | Gebi | William | Stanley |
|---|---|---|---|---|---|
| Sun 25 | Features decided ✅ | C4 outline | Check Wokwi parts | Sketch logic | Draft C3 |
| Mon 26 | All contracts published; P2 scope decided | Background, problem | C1 by 12:00, build circuit | Read sensors, C2 by 18:00 | HiveMQ, C3 by 18:00, fake publisher |
| Tue 27 | Inputs drive outputs; dashboard on fake data | Why IoT, target user | Finish wiring, block diagram | Alert logic, MQTT publish | Dashboard |
| Wed 28 | **Integration; feature freeze 20:00** | Video script | Fix wiring | Debug, stabilise | Real data, write ≥3 tests |
| Thu 29 | Report draft, video, screenshots complete | Record video, assemble report | Wiring screenshots, GPIO table | Clean code, Serial screenshots | Run tests, screenshots |
| Fri 30 | **Submit** (one day buffer before 31 Oct) | Proofread, submit | Check Wokwi link | Final code | Final dashboard screenshots |

---

## 10. Definition of done (submission checklist)

From the official Stage 2 guideline:

- [ ] `.docx` report following the template (no slides)
- [ ] Wokwi project link that opens and runs
- [ ] Source code / sketch
- [ ] Demo video `.mp4`
- [ ] Test screenshots
- [ ] ESP32 as main controller, ≥1 input, ≥1 output, Serial Monitor used
- [ ] ≥3 test scenarios incl. abnormal case, with input / expected / actual / status
- [ ] MQTT via HiveMQ + Python (paho-mqtt) dashboard with Plotly/Matplotlib
- [ ] Every component has a technical reason; every stand-in part is explained
- [ ] Section 12 lists real contributions of all four members

---

## 11. Git conventions

Keep it light: we have 5 days, so these rules exist only to stop us breaking `main` and overwriting each other.

### Branches

- **`main` always works**: Wokwi opens and runs, the dashboard starts. Nobody pushes code to `main` directly.
- One short-lived branch per task, merged within a day, deleted after merge. Pull `main` before you start.
- Name: **`<name>/<type>/<short-desc>`**, all lowercase, words joined with `-`.

| Example | Who |
|---|---|
| `kezia/docs/latar-belakang` | Kezia |
| `gebi/feat/wokwi-circuit` | Gebi |
| `william/feat/alert-logic` | William |
| `stanley/feat/live-dashboard` | Stanley |
| `gebi/contract/c1-pin-map` | contract owner only |
| `william/fix/buzzer-pin` | after freeze: only `fix` branches |

- **Exception:** your own section of `STATUS.md` may be pushed straight to `main` (it changes daily and touches nobody else).
- **After feature freeze (Wed 28, 20:00):** only `fix/` branches, and each fix is agreed in the group first.

### Commit messages

Format: **`<type>(<scope>): <what changed>`** — English, imperative ("add", not "added"), ≤ 72 characters, no full stop.

| Type | Use for |
|---|---|
| `feat` | new behaviour (sensor read, alert, dashboard chart) |
| `fix` | bug fix |
| `docs` | report text, README, AGENTS.md, STATUS.md |
| `test` | test scenarios, results, test screenshots |
| `contract` | a change to C1–C4 (needs all four 👍 first, §5) |
| `chore` | repo setup, `.gitignore`, dependencies |

Scopes: `firmware`, `wiring`, `dashboard`, `mqtt`, `tests`, `report`, `video`, `research`, `c1`–`c4`, `repo`.

```
feat(firmware): trigger vibration when step-down > 15 cm
fix(wiring): move buzzer from GPIO 2 to GPIO 25
feat(dashboard): plot distance_cm live from device/status
test(tests): add abnormal case for sensor timeout
docs(report): draft section 1 latar belakang
contract(c3): add LOW_BATTERY event
```

A `contract(...)` commit says in its body when the team approved it, e.g. `Approved by all four in group, Mon 26 Oct 17:40`.

### Pull requests

- Title uses the same format as a commit message.
- Reviewer is your pair from §3 (Gebi → William, William → Gebi, Stanley → William, Kezia → Stanley). Review within 6 hours.
- Fill in the PR template (`.github/pull_request_template.md`): what changed, how it was tested in Wokwi, whether a contract is touched.
- **Squash and merge**, so `main` gets one clean commit per task. Delete the branch afterwards.
- **Only humans merge.** AI agents open PRs; they never merge, approve, or push to `main`.

### Names in files and code

| Thing | Convention | Example |
|---|---|---|
| Folders and general files | lowercase, `-` or `_` as already used in the repo | `test_scenarios.md` |
| Wokwi files | fixed names (Wokwi needs them) | `sketch.ino`, `diagram.json` |
| Contracts | `C<n>_<topic>.md` | `C1_pin_map.md` |
| Report section drafts | `report/sections/NN_short-title.docx` (C4) | `07_logika-program.docx` |
| Final report | `report/final/FAHHH_SIC8_Stage2_Laporan.docx` | |
| Screenshots | `assets/screenshots/R<role>_<topic>_<nn>.png` (C4) | `R4_test_03.png` |
| Diagrams | `assets/diagrams/<name>.png` (C4) | `block-diagram.png` |
| Firmware pins and constants | `UPPER_SNAKE_CASE`, pins start with `PIN_` | `PIN_TRIG`, `STEP_DOWN_CM` |
| Firmware functions and variables | `camelCase` | `readDistance()`, `alertState` |
| Python | `snake_case` files, functions and variables | `fake_publisher.py`, `on_message()` |
| MQTT topics | lowercase, `/`-separated, prefix `sic8/fahhh/` (C3) | `sic8/fahhh/device/events` |
| Event and state names | `UPPER_SNAKE_CASE` (C2/C3) | `BOARDING_GAP`, `WARNING` |
| JSON keys | `snake_case` (C3) | `distance_cm`, `device_id` |

**`.docx` files can't be merged by Git.** Only the writer of a section edits that section file; only Kezia edits `report/final/`. If two people need the same `.docx`, agree in the group first.
