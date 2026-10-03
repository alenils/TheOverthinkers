#!/usr/bin/env python3
"""Generates live status JSON for the Matrix OS Hermes Control Center app."""

import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
from typing import Any, Dict, List
import yaml

HERMES_HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
HEALTH_DIR = Path(os.environ.get("HEALTH_DIR", Path.home() / "health"))
APPS_DIR = Path.home() / "apps" / "hermes"


def get_gateway_info() -> Dict[str, Any]:
    try:
        res = subprocess.run(["pgrep", "-f", "hermes.*gateway run"], capture_output=True, text=True)
        pids = [int(p) for p in res.stdout.strip().split() if p.isdigit()]
        if pids:
            return {"running": True, "pid": pids[0], "status": "active (running)"}
    except Exception:
        pass
    return {"running": False, "pid": None, "status": "inactive"}


def get_config_info() -> Dict[str, Any]:
    cfg_path = HERMES_HOME / "config.yaml"
    if not cfg_path.is_file():
        return {}
    try:
        return yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def get_cron_jobs() -> List[Dict[str, Any]]:
    jobs = []
    try:
        res = subprocess.run(["hermes", "cron", "list"], capture_output=True, text=True)
        lines = res.stdout.splitlines()
        current_job: Dict[str, Any] = {}
        for line in lines:
            line_str = line.strip()
            if re.match(r"^[0-9a-f]{8,}\s+\[active\]", line_str):
                if current_job:
                    jobs.append(current_job)
                current_job = {"id": line_str.split()[0], "status": "active"}
            elif line_str.startswith("Name:"):
                current_job["name"] = line_str.split(":", 1)[1].strip()
            elif line_str.startswith("Schedule:"):
                current_job["schedule"] = line_str.split(":", 1)[1].strip()
            elif line_str.startswith("Next run:"):
                current_job["next_run"] = line_str.split(":", 1)[1].strip()
        if current_job:
            jobs.append(current_job)
    except Exception:
        pass
    return jobs


def get_ledger_data() -> Dict[str, Any]:
    ledger_db = HEALTH_DIR / "data" / "ledger.db"
    if not ledger_db.is_file():
        return {"total_entries": 0, "entries": []}
    try:
        conn = sqlite3.connect(str(ledger_db))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, date, trigger_metric, deviation_sigma, attributed_cause,
                   intervention_type, cause_id, intervention_id, subjective_rating,
                   rebound_status, next_day_rebound_delta, created_at
            FROM stress_ledger
            ORDER BY created_at DESC
            LIMIT 15
            """
        ).fetchall()
        entries = [dict(r) for r in rows]
        total = conn.execute("SELECT COUNT(*) FROM stress_ledger").fetchone()[0]
        confirmed = conn.execute("SELECT COUNT(*) FROM stress_ledger WHERE rebound_status = 'REBOUND_CONFIRMED'").fetchone()[0]
        conn.close()
        return {
            "total_entries": total,
            "confirmed_rebounds": confirmed,
            "recovery_rate_pct": round((confirmed / total * 100), 1) if total > 0 else 0.0,
            "entries": entries,
        }
    except Exception as e:
        return {"error": str(e), "total_entries": 0, "entries": []}


def get_memory_info() -> Dict[str, Any]:
    mem_p = HERMES_HOME / "memories" / "MEMORY.md"
    user_p = HERMES_HOME / "memories" / "USER.md"
    soul_p = HERMES_HOME / "SOUL.md"
    return {
        "has_soul": soul_p.is_file(),
        "has_user": user_p.is_file(),
        "has_memory": mem_p.is_file(),
        "memory_preview": mem_p.read_text(encoding="utf-8")[:400] if mem_p.is_file() else "",
    }


def generate_status() -> Dict[str, Any]:
    cfg = get_config_info()
    model_cfg = cfg.get("model", {})
    tts_cfg = cfg.get("tts", {})
    gemini_tts = tts_cfg.get("gemini", {})
    gateway_info = get_gateway_info()
    skills_cfg = cfg.get("skills", {}).get("config", {})

    status = {
        "timestamp": subprocess.getoutput("date -u +'%Y-%m-%dT%H:%M:%SZ'"),
        "agent": {
            "name": "The Overthinkers Coach",
            "persona": "The Self-Distanced Observer",
            "runtime": "Hermes Agent",
            "max_turns": 3,
            "silence_by_default": True,
        },
        "model": {
            "provider": model_cfg.get("provider", "gemini"),
            "default": model_cfg.get("default", "gemini-3.8-flash"),
            "base_url": model_cfg.get("base_url", "https://generativelanguage.googleapis.com/v1beta"),
        },
        "tts": {
            "provider": tts_cfg.get("provider", "gemini"),
            "model": gemini_tts.get("model", "gemini-3.8-flash-tts"),
            "voice": gemini_tts.get("voice", "Kore"),
        },
        "gateway": gateway_info,
        "cron_jobs": get_cron_jobs(),
        "proactive_settings": {
            "timezone": skills_cfg.get("proactive", {}).get("timezone", "UTC"),
            "quiet_hours": skills_cfg.get("proactive", {}).get("quiet_hours", "08:00-21:00"),
            "baseline_window_days": 28,
            "anomaly_sigma": 1.5,
        },
        "skills": [
            {
                "name": "detect-baseline",
                "status": "enabled",
                "description": "28-day rolling baseline (μ ± 1.5σ) and athletic strain confounder filter",
            },
            {
                "name": "stress-dialogue",
                "status": "enabled",
                "description": "Cognitive appraisal triage (Distress vs. Eustress vs. Drain), ≤ 3 turn ceiling",
            },
            {
                "name": "stress-ledger",
                "status": "enabled",
                "description": "Outcome ledger, next-day biometric rebound verification, MEMORY writeback",
            },
            {
                "name": "samsung-health-import",
                "status": "enabled",
                "description": "Parser and normalizer for Samsung Health export archives",
            },
            {
                "name": "garmin-import",
                "status": "enabled",
                "description": "Parser and normalizer for Garmin Connect exports",
            },
            {
                "name": "peer-review",
                "status": "enabled",
                "description": "Multi-agent gut check and quality review runner",
            },
        ],
        "ledger": get_ledger_data(),
        "profiles": get_memory_info(),
        "quick_commands": [
            {
                "label": "Interactive Chat",
                "command": "hermes",
                "description": "Launch live terminal session with Gemini 3.8 Flash",
            },
            {
                "label": "Simulate Anomaly Check-In",
                "command": "python3 ~/overthinkers/scripts/simulate_trigger.py --metric hrv --deviation -2.2 --interactive",
                "description": "Test Gate 0 Steel Thread check-in in terminal",
            },
            {
                "label": "Weekly Recovery Recap",
                "command": "python3 ~/overthinkers/scripts/orchestrator.py --recap",
                "description": "View verified intervention recovery trends",
            },
            {
                "label": "Run Daily Orchestrator",
                "command": "python3 ~/overthinkers/scripts/orchestrator.py --interactive",
                "description": "Run baseline check & cognitive dialogue manually",
            },
            {
                "label": "Pair Telegram Bot",
                "command": "hermes gateway setup telegram",
                "description": "Enable 24/7 mobile stress check-ins via Telegram",
            },
            {
                "label": "Pair WhatsApp Bot",
                "command": "hermes gateway setup whatsapp",
                "description": "Enable 24/7 mobile stress check-ins via WhatsApp",
            },
        ],
    }

    return status


def main() -> None:
    data = generate_status()
    json_str = json.dumps(data, indent=2)

    # Write to local public & dist dirs if present
    for target in [APPS_DIR / "public" / "status.json", APPS_DIR / "dist" / "status.json"]:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json_str, encoding="utf-8")
        print(f"Wrote status JSON to {target}")


if __name__ == "__main__":
    main()
