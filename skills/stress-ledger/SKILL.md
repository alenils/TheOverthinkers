---
name: stress-ledger
description: "Maintains the closed-loop stress outcome ledger, verifies next-day biometric rebound, and updates personal memory."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, darwin]
metadata:
  hermes:
    config:
      - key: health.health_db
        description: "Path to SQLite health metrics database"
        default: "~/health/health.db"
      - key: health.garmin_db
        description: "Path to Garmin SQLite database"
        default: "~/health/garmin.db"
      - key: stress.ledger_db
        description: "SQLite database for stress outcome ledger"
        default: "data/ledger.db"
      - key: stress.memory_path
        description: "Path to persistent Profile/MEMORY.md document"
        default: "Profile/MEMORY.md"
    tags: [ledger, verification, closed-loop, memory, reflection]
---

# Stress Ledger & Closed-Loop Adaptation Engine

Closes the empirical loop by recording stress check-in actions, evaluating subsequent night biometric rebound, and adapting personal memory under strict context rent rules.

## Core Commands

1. **Record a Check-in:**
   ```bash
   python3 ${HERMES_SKILL_DIR}/scripts/ledger.py add TRIGGER CAUSE INTERVENTION --db ${stress.ledger_db}
   ```
   Or ingest directly from a dialogue session output:
   ```bash
   python3 ${HERMES_SKILL_DIR}/scripts/ledger.py ingest session_summary.json --db ${stress.ledger_db}
   ```

2. **Verify Next-Day Biometric Recovery:**
   Runs as part of the morning loop to inspect subsequent night vitals:
   ```bash
   python3 ${HERMES_SKILL_DIR}/scripts/ledger.py verify --next-day --db ${stress.ledger_db} --health-db ${health.health_db} --garmin-db ${health.garmin_db}
   ```

3. **Generate Recovery Report & Stats:**
   ```bash
   python3 ${HERMES_SKILL_DIR}/scripts/ledger.py report --db ${stress.ledger_db}
   ```

4. **Reflect & Adapt Personal Memory (`stress.memory_path`):**
   Writes verified habit efficacy into persistent memory under strict context rent:
   ```bash
   python3 ${HERMES_SKILL_DIR}/scripts/ledger.py reflect --db ${stress.ledger_db} --memory-path ${stress.memory_path}
   ```

5. **Weekly 1-Line Recap:**
   ```bash
   python3 ${HERMES_SKILL_DIR}/scripts/ledger.py recap --db ${stress.ledger_db}
   ```
