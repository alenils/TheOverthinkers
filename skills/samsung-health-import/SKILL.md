---
name: samsung-health-import
description: "Ingests Samsung Health export archives and normalizes daily autonomic metrics and workouts into local SQLite storage."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, darwin]
metadata:
  hermes:
    config:
      - key: health.health_dir
        description: "Root directory for health data and archives"
        default: "~/health"
      - key: health.health_db
        description: "SQLite database file for normalized health records"
        default: "~/health/health.db"
    tags: [wearable, ingest, samsung, health]
---

# Samsung Health Import

Ingests Samsung Health export archives, extracts sleep architecture, vagal tone (HRV), and exercise load, and stores normalized daily records into SQLite.

## Usage

Run the import script against a directory or specific archive:

```bash
python3 ${HERMES_SKILL_DIR}/scripts/import_samsung.py --zip-path /path/to/samsung_health_export.zip --db-path data/health.db
```

Or scan the export watch directory configured in `health.health_dir`:

```bash
python3 ${HERMES_SKILL_DIR}/scripts/import_samsung.py --dir ${health.health_dir}/samsung-exports --db-path ${health.health_db}
```

The script populates the `daily_metrics` table with:
- `date`: Record date in ISO format (`YYYY-MM-DD`).
- `hrv_score`: Nightly autonomic tone.
- `resting_hr`: Nightly resting pulse rate.
- `sleep_fragmentation`: Ratio of awakenings to total sleep time.
- `workout_strain_score`: Accumulated athletic exertion score.
- `source`: Identifier string (`samsung`).
