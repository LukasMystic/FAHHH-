# FAHHH? · SIC Batch 8 Stage 2

**Carried IoT device that helps blind and low-vision passengers move safely through Jakarta train stations.**

Samsung Innovation Campus Batch 8 · Selection Phase 2 — *IoT: Device and Hardware Discovery* · BINUS University · SDG 10 (Reduced Inequalities)

> Contributors and AI agents: read [`AGENTS.md`](AGENTS.md) first. Branching, commit and naming rules are in §11.

## Features (Stage 2)

| ID | Feature | Priority |
|---|---|---|
| P1 | Boarding and alighting assist | Primary |
| P2 | Guidance to the platform | Primary |
| P3 | Safety alerts work on the device (no signal needed) | Primary |
| S1 | Ground-level change alert | Secondary |
| S2 | Emergency button | Secondary |

## System flow

```
Sensors → ESP32 (logic) → Vibration / buzzer alerts
                ↓
      Serial + MQTT → HiveMQ public broker → Python dashboard (companion)
```

## Team

| Role | Member |
|---|---|
| Lead, Problem & Report | Kezia |
| Hardware & Wiring | Gebi |
| Firmware & Logic | William |
| Connectivity, Dashboard & Testing | Stanley |

## Repository

| Folder | What's inside | Owner |
|---|---|---|
| `contracts/` | Interfaces between roles (pins, logic, MQTT, report) | one owner per file |
| `firmware/` | ESP32 sketch + Wokwi `diagram.json` | William (code), Gebi (circuit) |
| `dashboard/` | MQTT subscriber, fake publisher, dashboard | Stanley |
| `tests/` | Test scenarios and results | Stanley |
| `research/` | Evidence and sources | Kezia |
| `report/` | Template, sections, final `.docx` | Kezia |
| `assets/` | Diagrams and screenshots | everyone |
| `video/` | Script and links (video files are not committed) | Kezia |

## Contributing

Full rules: [`AGENTS.md` §11](AGENTS.md#11-git-conventions). The short version:

### Branch names

`<name>/<type>/<short-desc>`, all lowercase, words joined with `-`.

```
william/feat/alert-logic
gebi/contract/c1-pin-map
kezia/docs/latar-belakang
stanley/fix/mqtt-reconnect
```

### Commit format

`<type>(<scope>): <what changed>` in English, imperative, ≤ 72 characters.

| Type | Use for |
|---|---|
| `feat` | new behaviour |
| `fix` | bug fix |
| `docs` | report, README, AGENTS.md, STATUS.md |
| `test` | test scenarios and results |
| `contract` | change to C1–C4 (all four 👍 first) |
| `chore` | repo setup, dependencies |

Scopes: `firmware` `wiring` `dashboard` `mqtt` `tests` `report` `video` `research` `c1`–`c4` `repo`

```
feat(firmware): trigger vibration when step-down > 15 cm
fix(wiring): move buzzer from GPIO 2 to GPIO 25
contract(c3): add LOW_BATTERY event
```

### Pull requests

1. Branch from the latest `main`.
2. Open a PR to `main`. The title uses the commit format, and the body follows the PR template.
3. Your reviewer pair approves within 6 hours: Gebi → William, William → Gebi, Stanley → William, Kezia → Stanley.
4. A **human** squash-merges and deletes the branch.

No direct pushes to `main` (exception: your own section of `STATUS.md`). After the feature freeze (Wed 28, 20:00), only `fix/` PRs agreed in the group.

### AI agents

AI agents **never merge and never push to `main`**. An agent may create a branch, commit, and open a PR only when its human allows it. The PR must say which member it works for. Merging is always done by a human after the reviewer approves.

### Naming

| Thing | Convention | Example |
|---|---|---|
| Contracts | `C<n>_<topic>.md` | `C1_pin_map.md` |
| Report sections | `report/sections/NN_short-title.docx` | `07_logika-program.docx` |
| Final report | `report/final/FAHHH_SIC8_Stage2_Laporan.docx` | |
| Screenshots | `assets/screenshots/R<role>_<topic>_<nn>.png` | `R4_test_03.png` |
| Diagrams | `assets/diagrams/<name>.png` | `block-diagram.png` |
| Firmware pins / constants | `UPPER_SNAKE_CASE`, pins start with `PIN_` | `PIN_TRIG` |
| Firmware functions / variables | `camelCase` | `readDistance()` |
| Python | `snake_case` | `fake_publisher.py` |
| MQTT topics | lowercase, prefix `sic8/fahhh/` | `sic8/fahhh/device/events` |
| Events / states | `UPPER_SNAKE_CASE` | `BOARDING_GAP` |
| JSON keys | `snake_case` | `distance_cm` |

`.docx` files can't be merged by Git: only the section's writer edits it, and only Kezia edits `report/final/`.

## Links

| Output | Link |
|---|---|
| Wokwi project | _TBD_ |
| Demo video | _TBD_ |

## Quick start

**Firmware:** open the Wokwi project link above, or copy `firmware/` into a new Wokwi ESP32 project. Copy `firmware/secrets.example.h` to `firmware/secrets.h` (defaults already point to the HiveMQ public broker — no login needed).

**Dashboard:**
```bash
python3 -m venv SIC && source SIC/bin/activate   # repo root, git-ignored
pip install -r dashboard/requirements.txt
cd dashboard
cp .env.example .env   # optional: defaults = HiveMQ public broker
python dashboard.py        # open http://127.0.0.1:8050
python fake_publisher.py   # second terminal: test data without the ESP32
```
