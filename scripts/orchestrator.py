#!/usr/bin/env python3
"""End-to-end orchestrator closing the Phase 1 loop.

Connects:
  Gate 1 (Ingest & Baseline Anomaly / Confounder Detection)
  Gate 2 (Cognitive Appraisal & 1 Micro-Action Triage)
  Gate 3 (Next-Day Biometric Verification, Outcome Ledger & Memory Reflection)
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "skills" / "detect-baseline" / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "skills" / "stress-dialogue" / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "skills" / "stress-ledger" / "scripts"))

import baseline_math  # noqa: E402
import dialogue_engine  # noqa: E402
import ledger  # noqa: E402
import simulate_trigger  # noqa: E402


def run_pipeline(
    target_date: str,
    health_db: Path,
    garmin_db: Optional[Path] = None,
    ledger_db: Path = Path("data/ledger.db"),
    memory_path: Path = Path("Profile/MEMORY.md"),
    state_file: Path = Path(".state/dispatch_state.json"),
    mock_reply: Optional[str] = None,
    interactive: bool = False,
    ignore_quiet_hours: bool = False,
    subjective_rating: Optional[int] = None,
) -> Dict[str, Any]:
    """Execute the full closed-loop daily cycle."""
    pipeline_report: Dict[str, Any] = {
        "date": target_date,
        "step_1_verification": None,
        "step_2_detection": None,
        "step_3_dialogue": None,
        "step_4_ledger_entry": None,
    }

    # Step 1 (Gate 3): Verify any pending interventions from previous days
    db_sources = [health_db]
    if garmin_db and garmin_db.is_file():
        db_sources.append(garmin_db)

    verified = ledger.verify_next_day_recovery(
        db_path=ledger_db,
        health_db_path=health_db,
        garmin_db_path=garmin_db if garmin_db and garmin_db.is_file() else None,
    )
    pipeline_report["step_1_verification"] = {
        "verified_count": len(verified),
        "details": verified,
    }
    if verified and memory_path.is_file():
        ledger.reflect_to_memory(ledger_db, memory_path)

    # Step 2 (Gate 1): Rolling baseline & confounder check for target date
    try:
        target_rec, prior_rec, history = baseline_math.load_unified_series(
            db_sources, target_date, window_days=28
        )
    except Exception as e:
        pipeline_report["step_2_detection"] = {"status": "ERROR", "error": str(e)}
        return pipeline_report

    if not target_rec:
        pipeline_report["step_2_detection"] = {
            "status": "NO_DATA",
            "message": f"No wearable data for {target_date}",
        }
        return pipeline_report

    eval_result = baseline_math.evaluate_day_metrics(
        target_rec=target_rec,
        prior_rec=prior_rec,
        history_recs=history,
    )
    pipeline_report["step_2_detection"] = eval_result

    # If baseline is normal or suppressed by workout strain -> silence by default!
    if not eval_result.get("dispatch_trigger"):
        return pipeline_report

    # Check quiet hours & once-per-day limit using user's local time
    now_local = datetime.now().astimezone()
    if not ignore_quiet_hours and not baseline_math.check_quiet_hours(now_local):
        pipeline_report["step_2_detection"]["dispatch_suppressed"] = "Quiet hours"
        return pipeline_report

    if not simulate_trigger.check_daily_dispatch(state_file, target_date):
        pipeline_report["step_2_detection"]["dispatch_suppressed"] = "Already dispatched today"
        return pipeline_report

    # Step 3 (Gate 2): Cognitive appraisal check-in
    dialogue_summary = dialogue_engine.run_dialogue(
        anomaly_payload=eval_result,
        mock_responses=[mock_reply] if mock_reply else None,
        interactive=interactive,
        subjective_rating=subjective_rating,
    )
    pipeline_report["step_3_dialogue"] = dialogue_summary

    # Record dispatch idempotency
    simulate_trigger.record_dispatch(state_file, target_date)

    # Step 4 (Gate 3): Ingest check-in into outcome ledger
    entry_id = ledger.add_ledger_entry(
        db_path=ledger_db,
        trigger_metric=dialogue_summary.get("trigger_metric", "hrv_score"),
        attributed_cause=dialogue_summary.get("attributed_cause", "Unspecified friction"),
        intervention_type=dialogue_summary.get("intervention_type", "Standard pause"),
        date_str=target_date,
        deviation_sigma=dialogue_summary.get("deviation_sigma", -1.5),
        cause_id=dialogue_summary.get("cause_id"),
        intervention_id=dialogue_summary.get("intervention_id"),
        subjective_rating=dialogue_summary.get("subjective_rating"),
    )
    pipeline_report["step_4_ledger_entry"] = {"entry_id": entry_id, "status": "RECORDED"}

    return pipeline_report


def main() -> int:
    parser = argparse.ArgumentParser(description="The Overthinkers closed-loop orchestrator.")
    parser.add_argument("--date", help="Target date YYYY-MM-DD (defaults to today)")
    parser.add_argument("--health-db", default="data/health.db", help="Path to health DB")
    parser.add_argument("--garmin-db", default="data/garmin.db", help="Path to Garmin DB")
    parser.add_argument("--ledger-db", default="data/ledger.db", help="Path to ledger DB")
    parser.add_argument("--memory-path", default="Profile/MEMORY.md", help="Path to MEMORY.md")
    parser.add_argument("--state-file", default=".state/dispatch_state.json", help="Path to state file")
    parser.add_argument("--mock-reply", help="Mock user reply string")
    parser.add_argument("--interactive", action="store_true", help="Interactive terminal dialogue")
    parser.add_argument("--ignore-quiet-hours", action="store_true", default=False, help="Bypass quiet hours")
    parser.add_argument("--recap", action="store_true", help="Print weekly trend recap and exit")

    args = parser.parse_args()

    ledger_path = Path(args.ledger_db)
    if args.recap:
        print(ledger.generate_weekly_recap(ledger_path))
        return 0

    target = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    report = run_pipeline(
        target_date=target,
        health_db=Path(args.health_db),
        garmin_db=Path(args.garmin_db) if Path(args.garmin_db).is_file() else None,
        ledger_db=ledger_path,
        memory_path=Path(args.memory_path),
        state_file=Path(args.state_file),
        mock_reply=args.mock_reply,
        interactive=args.interactive,
        ignore_quiet_hours=args.ignore_quiet_hours,
    )

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
