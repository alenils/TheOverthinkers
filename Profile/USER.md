# Tier 2: The Human Context (`USER.md`)

This document holds the durable operational facts regarding the human user. It pays context rent on active sessions.

---

## Biometric Configuration & Storage

* **Active Wearable Sources:** Samsung Health (`samsung`), Garmin Connect (`garmin`)
* **Primary Database Targets:**
  * Samsung Health store: `data/health.db`
  * Garmin Connect store: `data/garmin.db`
* **Baseline Window:** Rolling 28-day window for individual mean and deviation calculations.
* **Biometric Thresholds:**
  * Anomaly trigger: deviation crossing $\pm 1.5\sigma$ from rolling mean.
  * Rebound verification target: recovery within $\pm 1.0\sigma$ of rolling mean.

---

## Cognitive Friction Profile

* **Typical Friction Patterns:**
  * Scope dilation and task paralysis on unstructured project milestones.
  * Evening recovery erosion: continuing problem rehearsal past bedtime.
  * Over-indexing on uncontrollable external blockers.
* **Effective Historical Reframes:**
  * Shifting from *"How do I finish everything?"* to *"What is the single invariant for today?"*
  * Physiological down-regulation (physiological sigh or short walk) before tactical planning.

---

## Physical Training & Confounder Profile

* **Activity Profile:**
  * Zone 2 aerobic base (3 sessions per week).
  * Strength resistance training (2 sessions per week).
* **Confounder Detection Parameters:**
  * Days where prior day training load / strain jumps significantly above regular baseline are categorized as *Physical Recovery Strain*.
  * On confirmed physical strain days, mental stress triage is suppressed.

---

## Communication & Guardrails

* **Notification Channel:** Hermes Proactive Gateway / Messaging CLI
* **Allowed Check-in Window (Quiet Hours):** `08:00-21:00`
* **Maximum Daily Proactive Check-ins:** 1
