import { StatusData } from "./types";

export const INITIAL_DATA: StatusData = {
  timestamp: "2026-10-03T17:00:00Z",
  agent: {
    name: "The Overthinkers Coach",
    persona: "The Self-Distanced Observer",
    runtime: "Hermes Agent",
    max_turns: 3,
    silence_by_default: true,
  },
  model: {
    provider: "gemini",
    default: "gemini-3.8-flash",
    base_url: "https://generativelanguage.googleapis.com/v1beta",
  },
  tts: {
    provider: "gemini",
    model: "gemini-3.8-flash-tts",
    voice: "Kore",
  },
  gateway: {
    running: true,
    status: "active (running)",
  },
  cron_jobs: [
    {
      id: "413215a49f12",
      status: "active",
      name: "overthinkers-morning-check",
      schedule: "0 8 * * *",
      next_run: "2026-10-04T08:00:00+00:00",
    },
  ],
  proactive_settings: {
    timezone: "UTC",
    quiet_hours: "08:00-21:00",
    baseline_window_days: 28,
    anomaly_sigma: 1.5,
  },
  skills: [
    {
      name: "detect-baseline",
      status: "enabled",
      description: "28-day rolling baseline (μ ± 1.5σ) and athletic strain confounder filter",
    },
    {
      name: "stress-dialogue",
      status: "enabled",
      description: "Cognitive appraisal triage (Distress vs. Eustress vs. Drain), ≤ 3 turn ceiling",
    },
    {
      name: "stress-ledger",
      status: "enabled",
      description: "Outcome ledger, next-day biometric rebound verification, MEMORY writeback",
    },
    {
      name: "samsung-health-import",
      status: "enabled",
      description: "Parser and normalizer for Samsung Health export archives",
    },
    {
      name: "garmin-import",
      status: "enabled",
      description: "Parser and normalizer for Garmin Connect exports",
    },
    {
      name: "peer-review",
      status: "enabled",
      description: "Multi-agent gut check and quality review runner",
    },
  ],
  ledger: {
    total_entries: 1,
    confirmed_rebounds: 0,
    recovery_rate_pct: 0.0,
    entries: [
      {
        id: 1,
        date: "2026-10-03",
        trigger_metric: "hrv_score",
        deviation_sigma: -1.8,
        attributed_cause: "Launch release deployment milestone",
        intervention_type: "Lock in single #1 priority milestone",
        cause_id: "CHALLENGE_LOAD",
        intervention_id: "PRIORITY_LOCK",
        subjective_rating: 8,
        rebound_status: "PENDING_VERIFICATION",
        next_day_rebound_delta: null,
      },
    ],
  },
  profiles: {
    has_soul: true,
    has_user: true,
    has_memory: true,
  },
  quick_commands: [
    {
      label: "Interactive Chat",
      command: "hermes",
      description: "Launch live terminal session with Gemini 3.8 Flash",
    },
    {
      label: "Simulate Anomaly Check-In",
      command: "python3 ~/overthinkers/scripts/simulate_trigger.py --metric hrv --deviation -2.2 --interactive",
      description: "Test Gate 0 Steel Thread check-in in terminal",
    },
    {
      label: "Weekly Recovery Recap",
      command: "python3 ~/overthinkers/scripts/orchestrator.py --recap",
      description: "View verified intervention recovery trends",
    },
    {
      label: "Run Daily Orchestrator",
      command: "python3 ~/overthinkers/scripts/orchestrator.py --interactive",
      description: "Run baseline check & cognitive dialogue manually",
    },
    {
      label: "Pair Telegram Bot",
      command: "hermes gateway setup telegram",
      description: "Enable 24/7 mobile stress check-ins via Telegram",
    },
    {
      label: "Pair WhatsApp Bot",
      command: "hermes gateway setup whatsapp",
      description: "Enable 24/7 mobile stress check-ins via WhatsApp",
    },
  ],
};
