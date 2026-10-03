---
name: detect-baseline
description: "Computes rolling baselines over wearable metrics and filters athletic workout strain confounders."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, darwin]
metadata:
  hermes:
    config:
      - key: health.health_db
        description: "Primary SQLite database for health data"
        default: "~/.hermes/data/health.db"
      - key: health.garmin_db
        description: "Garmin SQLite database for health data"
        default: "~/.hermes/data/garmin.db"
      - key: stress.baseline_window_days
        description: "Rolling baseline history window in days"
        default: "28"
      - key: stress.anomaly_sigma
        description: "Standard deviation threshold for slope break detection"
        default: "1.5"
      - key: stress.workout_strain_threshold
        description: "Workout strain threshold that suppresses mental stress triage"
        default: "14.0"
      - key: stress.quiet_hours
        description: "Allowed window for proactive check-in delivery"
        default: "08:00-21:00"
    tags: [baseline, anomaly-detection, confounder-filter, coaching]
---

# Detect Baseline & Confounder Engine

Evaluates daily biometric records against individual rolling baselines (14 to 28 days), detecting slope breaks on autonomic tone and sleep fragmentation while filtering athletic exertion confounders.

## Core Rules

1. **Compare Against Own Baseline, Never Population Norms:**
   Calculates rolling mean and standard deviation over an individual 14 to 28 day window. Level and daily step-change thresholds are distinct heuristics. Daily deltas require consecutive same-source readings with nonzero variance; gaps use only level deviations.

2. **Workout Confounder Interlock:**
   If the prior day recorded a high athletic load or workout strain jump, the autonomic dip is categorized as **Physical Recovery Strain**. The agent logs recovery status and stays completely silent.

3. **Silence by Default:**
   Proactive alerts occur at most once per day, strictly when an unconfounded anomaly is confirmed. Normal variance equals silence.

## Execution

Check a specific date:

```bash
python3 ${HERMES_SKILL_DIR}/scripts/baseline_math.py check --date 2026-10-03 --db-path ${health.health_db}
```

Keep source and metric definitions separate: Samsung inverted stress indices and Garmin HRV are not interchangeable. Require at least 14 valid readings per source and metric. Missing workout context or insufficient same-source workout history suppresses proactive outreach and retains explicit uncertainty. Physical load is a possible contributing factor, not a proven cause.
