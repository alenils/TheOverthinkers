---
name: garmin-import
description: "Ingests Garmin Connect account-export archives and normalizes daily autonomic metrics and workouts into local SQLite storage."
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
      - key: health.garmin_db
        description: "SQLite database file for normalized Garmin records"
        default: "~/health/garmin.db"
    tags: [wearable, ingest, garmin, health]
---

# Garmin Import

Ingests Garmin Connect account export archives, parsing daily wellness JSON records (sleep fragmentation, nightly HRV, resting HR) and activity session records into a normalized SQLite database.

## Usage

Run the import script against a Garmin Connect export archive:

```bash
python3 ${HERMES_SKILL_DIR}/scripts/import_garmin.py --zip-path /path/to/garmin_connect_export.zip --db-path data/garmin.db
```

Or scan the export directory configured in `health.health_dir`:

```bash
python3 ${HERMES_SKILL_DIR}/scripts/import_garmin.py --dir ${health.health_dir}/garmin-exports --db-path ${health.garmin_db}
```

The script populates the `daily_metrics` table with:
- `date`: Record date in ISO format (`YYYY-MM-DD`).
- `hrv_score`: Nightly autonomic tone.
- `resting_hr`: Nightly resting pulse rate.
- `sleep_fragmentation`: Ratio of awakenings to total sleep time.
- `workout_strain_score`: Accumulated athletic exertion score.
- `source`: Identifier string (`garmin`).
