# FAHHH? · SIC Batch 8 Stage 2

**Carried IoT device that helps blind and low-vision passengers move safely through Jakarta train stations.**

Samsung Innovation Campus Batch 8 · Selection Phase 2 — *IoT: Device and Hardware Discovery* · BINUS University · SDG 10 (Reduced Inequalities)

> Contributors and AI agents: read [`AGENTS.md`](AGENTS.md) first.

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
      Serial + MQTT → HiveMQ Cloud → Python dashboard (companion)
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

## Links

| Output | Link |
|---|---|
| Wokwi project | _TBD_ |
| Demo video | _TBD_ |

## Quick start

**Firmware:** open the Wokwi project link above, or copy `firmware/` into a new Wokwi ESP32 project. Copy `firmware/secrets.example.h` to `firmware/secrets.h` and add the HiveMQ credentials (ask Stanley privately).

**Dashboard:**
```bash
cd dashboard
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add HiveMQ credentials
python fake_publisher.py   # optional: test data without the ESP32
```
