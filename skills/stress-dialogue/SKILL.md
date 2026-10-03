---
name: stress-dialogue
description: "Executes a self-distanced check-in and cognitive appraisal when an anomaly is detected."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, darwin]
metadata:
  hermes:
    config:
      - key: stress.max_turns
        description: "Hard cap on conversational turns to prevent rumination"
        default: "3"
      - key: stress.quiet_hours
        description: "Time window when proactive pings are allowed"
        default: "08:00-21:00"
    tags: [stress, appraisal, coaching]
---

# Stress Dialogue & Cognitive Appraisal Engine

Connects wearable autonomic anomalies to subjective meaning using a 3rd-person self-distanced observer stance and cognitive appraisal triage.

## Appraisal Matrix

When an autonomic dip is detected and confirmed unconfounded by prior-day workout strain, the coach initiates a concise dialogue bounded to `stress.max_turns`:

1. **Context Extraction:**
   The user identifies the primary friction point (workload, interpersonal tension, fatigue, uncertainty).

2. **Cognitive Appraisal:**
   - **Eustress (High Control / Challenge):** Reinforce productive engagement; prescribe single-task focus or boundary defense.
   - **Distress (Low Control / Threat):** Prescribe immediate nervous system down-regulation (physiological sigh, 5-minute outdoor walk, box breathing, grounding).
   - **Recovery Drain (Chronic Fatigue / Accumulated Deficit):** Prescribe active rest, evening boundary defense, or an early sleep window.
   - **Uncertain (Ambiguous Context):** Ask exactly 1 clarifying question before prescribing a grounding micro-action.

3. **Micro-Action Commitment:**
   Locks in exactly 1 concrete step and closes the dialogue immediately.

## Anti-Rumination Circuit Breaker

The dialogue is strictly capped at `stress.max_turns` (maximum 3 turns total). If cyclic venting or catastrophizing is detected, the agent interrupts the loop, grounds the user, prescribes a down-regulation action, and terminates the session.

## Usage

Run an appraisal check-in session:

```bash
python3 ${HERMES_SKILL_DIR}/scripts/dialogue_engine.py --anomaly-json '{"triggered_metric": "hrv_score", "deviation_sigma": -1.8, "date": "2026-10-03"}'
```
