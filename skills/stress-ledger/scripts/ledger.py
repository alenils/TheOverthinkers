#!/usr/bin/env python3
"""Closed-loop outcome ledger and personal adaptation engine.

Tracks stress interventions, verifies next-day biometric recovery against
the rolling baseline, and updates Profile/MEMORY.md under context rent rules.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import sqlite3
import sys
from typing import Any, Dict, List, Optional, Tuple

SKILL_DETECT_DIR = Path(__file__).resolve().parent.parent.parent / "detect-baseline" / "scripts"
if SKILL_DETECT_DIR.is_dir():
    sys.path.insert(0, str(SKILL_DETECT_DIR))
    import baseline_math
else:
    import baseline_math  # noqa: E402


def init_ledger_db(db_path: Path) -> sqlite3.Connection:
    """Initialize SQLite outcome ledger database."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    with conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS stress_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                trigger_metric TEXT NOT NULL,
                deviation_sigma REAL NOT NULL,
                attributed_cause TEXT NOT NULL,
                cause_id TEXT,
                intervention_type TEXT NOT NULL,
                intervention_id TEXT,
                subjective_rating INTEGER,
                next_day_date TEXT,
                next_day_metric_val REAL,
                next_day_sigma REAL,
                next_day_rebound_delta REAL,
                rebound_status TEXT DEFAULT 'PENDING_VERIFICATION',
                created_at TEXT NOT NULL,
                verified_at TEXT
            )
            """
        )
    return conn


def add_ledger_entry(
    db_path: Path,
    trigger_metric: str,
    attributed_cause: str,
    intervention_type: str,
    date_str: Optional[str] = None,
    deviation_sigma: float = -1.5,
    cause_id: Optional[str] = None,
    intervention_id: Optional[str] = None,
    subjective_rating: Optional[int] = None,
) -> int:
    """Record a new check-in entry into the ledger."""
    conn = init_ledger_db(db_path)
    now_iso = datetime.now(timezone.utc).isoformat()
    d = date_str or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    with conn:
        cur = conn.execute(
            """
            INSERT INTO stress_ledger (
                date, trigger_metric, deviation_sigma, attributed_cause,
                cause_id, intervention_type, intervention_id, subjective_rating,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                d,
                trigger_metric,
                deviation_sigma,
                attributed_cause,
                cause_id,
                intervention_type,
                intervention_id,
                subjective_rating,
                now_iso,
            ),
        )
        row_id = cur.lastrowid or 0
    conn.close()
    return row_id


def ingest_session_json(db_path: Path, session_json_path: Path) -> int:
    """Ingest a Gate 2 dialogue summary JSON into the outcome ledger."""
    data = json.loads(session_json_path.read_text(encoding="utf-8"))
    metric = data.get("trigger_metric") or data.get("triggered_metric") or data.get("metric") or "hrv_score"
    return add_ledger_entry(
        db_path=db_path,
        trigger_metric=metric,
        attributed_cause=data.get("attributed_cause", "Unspecified friction"),
        intervention_type=data.get("intervention_type", "Standard pause"),
        date_str=data.get("date"),
        deviation_sigma=data.get("deviation_sigma", -1.5),
        cause_id=data.get("cause_id"),
        intervention_id=data.get("intervention_id"),
        subjective_rating=data.get("subjective_rating"),
    )


def verify_next_day_recovery(
    db_path: Path,
    health_db_path: Path,
    garmin_db_path: Optional[Path] = None,
    min_history_days: int = 14,
) -> List[Dict[str, Any]]:
    """Verify subsequent night biometric recovery for pending ledger records.

    Baseline history excludes the trigger day to prevent baseline contamination.
    Correctly accounts for metric directionality:
    - HRV: higher is better; rebound is next_sigma >= -1.0
    - Sleep Fragmentation: lower is better; rebound is next_sigma <= +1.0
    """
    conn = init_ledger_db(db_path)
    conn.row_factory = sqlite3.Row

    with conn:
        pending_rows = conn.execute(
            """
            SELECT * FROM stress_ledger
            WHERE rebound_status = 'PENDING_VERIFICATION'
            ORDER BY date ASC
            """
        ).fetchall()

    if not pending_rows:
        conn.close()
        return []

    verified_results: List[Dict[str, Any]] = []
    db_sources = [health_db_path]
    if garmin_db_path and garmin_db_path.is_file():
        db_sources.append(garmin_db_path)

    now_iso = datetime.now(timezone.utc).isoformat()

    with conn:
        for row in pending_rows:
            rec_id = row["id"]
            checkin_date = row["date"]
            dt_checkin = datetime.strptime(checkin_date, "%Y-%m-%d")
            next_date = (dt_checkin + timedelta(days=1)).strftime("%Y-%m-%d")

            # Load next day record and historical baseline
            target_rec, _, history = baseline_math.load_unified_series(
                db_sources, next_date, window_days=28
            )

            if not target_rec:
                days_pending = (datetime.now(timezone.utc) - dt_checkin.replace(tzinfo=timezone.utc)).days
                if days_pending > 7:
                    conn.execute(
                        """
                        UPDATE stress_ledger
                        SET rebound_status = 'EXPIRED_NO_DATA',
                            verified_at = ?
                        WHERE id = ?
                        """,
                        (now_iso, rec_id),
                    )
                continue

            metric_key = row["trigger_metric"]
            next_val = target_rec.get(metric_key)
            if next_val is None:
                continue

            # Crucial: Exclude the check-in/anomaly day itself to prevent baseline contamination!
            metric_history = [
                float(h[metric_key])
                for h in history
                if h.get(metric_key) is not None and h["date"] != checkin_date
            ]
            if len(metric_history) < min_history_days:
                continue

            mean, std = baseline_math.compute_mean_and_std(metric_history)
            next_sigma = baseline_math.compute_z_score(float(next_val), mean, std)
            initial_sigma = row["deviation_sigma"]

            # Evaluate directionality
            if metric_key == "sleep_fragmentation":
                # For sleep fragmentation: lower is better. Anomaly is high spike (z >= +1.5).
                # Rebound delta is positive when fragmentation decreased toward or below mean.
                rebound_delta = round(initial_sigma - next_sigma, 2)
                if next_sigma <= 1.0:
                    rebound_status = "REBOUND_CONFIRMED"
                elif next_sigma < initial_sigma:
                    rebound_status = "PARTIAL_REBOUND"
                else:
                    rebound_status = "NO_REBOUND"
            else:
                # For HRV: higher is better. Anomaly is drop (z <= -1.5).
                # Rebound delta is positive when HRV rebounded upward toward mean.
                rebound_delta = round(next_sigma - initial_sigma, 2)
                if next_sigma >= -1.0:
                    rebound_status = "REBOUND_CONFIRMED"
                elif next_sigma > initial_sigma:
                    rebound_status = "PARTIAL_REBOUND"
                else:
                    rebound_status = "NO_REBOUND"

            conn.execute(
                """
                UPDATE stress_ledger
                SET next_day_date = ?,
                    next_day_metric_val = ?,
                    next_day_sigma = ?,
                    next_day_rebound_delta = ?,
                    rebound_status = ?,
                    verified_at = ?
                WHERE id = ?
                """,
                (
                    next_date,
                    round(float(next_val), 2),
                    round(next_sigma, 2),
                    rebound_delta,
                    rebound_status,
                    now_iso,
                    rec_id,
                ),
            )

            verified_results.append({
                "id": rec_id,
                "date": checkin_date,
                "next_day_date": next_date,
                "metric": metric_key,
                "initial_sigma": initial_sigma,
                "next_sigma": round(next_sigma, 2),
                "rebound_delta": rebound_delta,
                "status": rebound_status,
            })

    conn.close()
    return verified_results


def get_ledger_report(db_path: Path) -> Dict[str, Any]:
    """Generate statistical summary of recorded, verified, and expired interventions."""
    conn = init_ledger_db(db_path)
    conn.row_factory = sqlite3.Row

    with conn:
        all_rows = conn.execute("SELECT * FROM stress_ledger ORDER BY date ASC").fetchall()
    conn.close()

    total = len(all_rows)
    verified = [
        r for r in all_rows
        if r["rebound_status"] in ("REBOUND_CONFIRMED", "PARTIAL_REBOUND", "NO_REBOUND")
    ]
    confirmed = [r for r in verified if r["rebound_status"] == "REBOUND_CONFIRMED"]
    expired = [r for r in all_rows if r["rebound_status"] == "EXPIRED_NO_DATA"]
    pending = [r for r in all_rows if r["rebound_status"] == "PENDING_VERIFICATION"]

    dates = [r["date"] for r in all_rows if r["date"] is not None]
    date_range = f"{min(dates)} to {max(dates)}" if dates else "none"

    # Group by intervention_id or intervention_type
    by_intervention: Dict[str, Dict[str, Any]] = {}
    for r in verified:
        int_key = r["intervention_id"] or r["intervention_type"]
        group = by_intervention.setdefault(int_key, {
            "count": 0,
            "confirmed": 0,
            "deltas": [],
            "ratings": [],
        })
        group["count"] += 1
        if r["rebound_status"] == "REBOUND_CONFIRMED":
            group["confirmed"] += 1
        if r["next_day_rebound_delta"] is not None:
            group["deltas"].append(r["next_day_rebound_delta"])
        if r["subjective_rating"] is not None:
            group["ratings"].append(r["subjective_rating"])

    efficacy_summary: Dict[str, Any] = {}
    for k, v in by_intervention.items():
        avg_delta = round(sum(v["deltas"]) / len(v["deltas"]), 2) if v["deltas"] else 0.0
        success_pct = round((v["confirmed"] / v["count"]) * 100.0, 1) if v["count"] > 0 else 0.0
        avg_rating = round(sum(v["ratings"]) / len(v["ratings"]), 1) if v["ratings"] else None
        efficacy_summary[k] = {
            "total_trials": v["count"],
            "has_minimum_sample": v["count"] >= 3,
            "success_rate_pct": success_pct,
            "avg_rebound_delta_sigma": avg_delta,
            "avg_subjective_rating": avg_rating,
        }

    return {
        "total_entries": total,
        "verified_entries": len(verified),
        "confirmed_rebounds": len(confirmed),
        "expired_entries": len(expired),
        "pending_entries": len(pending),
        "date_range": date_range,
        "overall_success_rate_pct": round((len(confirmed) / len(verified) * 100.0), 1) if verified else 0.0,
        "interventions": efficacy_summary,
    }


def reflect_to_memory(db_path: Path, memory_path: Path) -> str:
    """Update Profile/MEMORY.md with observed follow-up associations under strict context rent."""
    report = get_ledger_report(db_path)
    if not memory_path.is_file():
        raise FileNotFoundError(f"Memory document not found: {memory_path}")

    lines: List[str] = []
    int_summary = report.get("interventions", {})

    id_to_label = {
        "PHYSIOLOGICAL_SIGH": "Physiological Sigh (3 cycles)",
        "OUTDOOR_WALK": "15-Minute Outdoor Walk",
        "PRIORITY_LOCK": "Task Boundary Defense (Top 1 Lock)",
        "SCREEN_CURFEW": "Screen Wind-down Curfew",
        "GROUNDING_PAUSE": "Grounding Device Pause",
    }

    if not int_summary:
        lines.append("* *Awaiting verified closed-loop ledger trials.*")
    else:
        for int_id, stats in sorted(int_summary.items(), key=lambda x: x[1]["avg_rebound_delta_sigma"], reverse=True):
            label = id_to_label.get(int_id, int_id.replace("_", " ").title())
            delta = stats["avg_rebound_delta_sigma"]
            rate = stats["success_rate_pct"]
            trials = stats["total_trials"]
            sign = "+" if delta >= 0 else ""

            if stats["has_minimum_sample"]:
                lines.append(
                    f"* **{label}:** Associated with {sign}{delta}σ follow-up rebound ({rate:.0f}% recovery rate over {trials} verified observations)."
                )
            else:
                lines.append(
                    f"* **{label}:** Observed in {trials} follow-up trial(s) (preliminary delta {sign}{delta}σ; sample too small for trend conclusion)."
                )

    new_section_content = (
        "## Intervention Follow-Up Ledger (Observed Biometric Associations)\n\n"
        f"Empirical follow-up observations (Date range: {report.get('date_range', 'n/a')}, "
        f"Verified: {report.get('verified_entries', 0)}, Expired: {report.get('expired_entries', 0)}):\n\n"
        + "\n".join(lines)
        + "\n"
    )

    content = memory_path.read_text(encoding="utf-8")
    # Match either title and preserve horizontal rules
    pattern = r"## Intervention (?:Efficacy|Follow-Up) Ledger[^\n]*\n.*?(?=\n---\n|\n## |\Z)"
    if re.search(pattern, content, flags=re.DOTALL):
        updated = re.sub(pattern, new_section_content.rstrip(), content, count=1, flags=re.DOTALL)
    else:
        updated = content + "\n\n" + new_section_content

    memory_path.write_text(updated, encoding="utf-8")
    return new_section_content


def generate_weekly_recap(db_path: Path) -> str:
    """Generate a single 1-line trend recap adhering to minimum sample rules."""
    report = get_ledger_report(db_path)
    interventions = report.get("interventions", {})
    verified_count = report.get("verified_entries", 0)

    if verified_count == 0 or not interventions:
        return "Weekly Recap: Zero verified anomaly follow-ups this week; vitals maintained steady baseline."

    sorted_ints = sorted(
        interventions.items(),
        key=lambda x: x[1]["avg_rebound_delta_sigma"],
        reverse=True,
    )
    best_id, best_stats = sorted_ints[0]
    best_name = best_id.replace("_", " ").title()
    delta = best_stats["avg_rebound_delta_sigma"]
    sign = "+" if delta >= 0 else ""
    trials = best_stats["total_trials"]

    if not best_stats["has_minimum_sample"]:
        return (
            f"Weekly Recap: {verified_count} follow-up check-in(s) recorded "
            f"(preliminary observations; awaiting >=3 trials per habit)."
        )

    if len(sorted_ints) > 1 and sorted_ints[1][1]["has_minimum_sample"]:
        second_id, second_stats = sorted_ints[1]
        second_name = second_id.replace("_", " ").title()
        return (
            f"Weekly Recap: {best_name} associated with {sign}{delta}σ follow-up rebound, "
            f"compared to {second_name} across {verified_count} verified trials."
        )

    return (
        f"Weekly Recap: {best_name} associated with {sign}{delta}σ follow-up rebound "
        f"across {trials} verified trials."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Stress outcome ledger CLI.")
    subparsers = parser.add_subparsers(dest="command")

    # 1. add
    add_p = subparsers.add_parser("add", help="Record a new check-in")
    add_p.add_argument("trigger", help="Trigger metric name")
    add_p.add_argument("cause", help="Attributed friction cause")
    add_p.add_argument("intervention", help="Prescribed micro-action")
    add_p.add_argument("--date", help="Check-in date YYYY-MM-DD")
    add_p.add_argument("--deviation", type=float, default=-1.5, help="Deviation sigma")
    add_p.add_argument("--cause-id", help="Canonical cause ID")
    add_p.add_argument("--intervention-id", help="Canonical intervention ID")
    add_p.add_argument("--rating", type=int, help="Subjective rating (1-10)")
    add_p.add_argument("--db", default="data/ledger.db", help="Path to ledger SQLite DB")

    # 2. ingest
    ingest_p = subparsers.add_parser("ingest", help="Ingest a dialogue session summary JSON")
    ingest_p.add_argument("json_file", help="Path to session summary JSON")
    ingest_p.add_argument("--db", default="data/ledger.db", help="Path to ledger SQLite DB")

    # 3. verify
    verify_p = subparsers.add_parser("verify", help="Verify next-day recovery")
    verify_p.add_argument("--next-day", action="store_true", default=True, help="Verify next day")
    verify_p.add_argument("--db", default="data/ledger.db", help="Path to ledger DB")
    verify_p.add_argument("--health-db", default="data/health.db", help="Path to health DB")
    verify_p.add_argument("--garmin-db", default="data/garmin.db", help="Path to garmin DB")
    verify_p.add_argument("--min-history-days", type=int, default=14, help="Min history days")

    # 4. report
    report_p = subparsers.add_parser("report", help="Report recovery stats")
    report_p.add_argument("--db", default="data/ledger.db", help="Path to ledger DB")

    # 5. reflect
    reflect_p = subparsers.add_parser("reflect", help="Reflect verified habits into MEMORY.md")
    reflect_p.add_argument("--db", default="data/ledger.db", help="Path to ledger DB")
    reflect_p.add_argument("--memory-path", default="Profile/MEMORY.md", help="Path to MEMORY.md")

    # 6. recap
    recap_p = subparsers.add_parser("recap", help="Output weekly 1-line recap")
    recap_p.add_argument("--db", default="data/ledger.db", help="Path to ledger DB")

    args = parser.parse_args()

    if args.command == "add":
        row_id = add_ledger_entry(
            db_path=Path(args.db),
            trigger_metric=args.trigger,
            attributed_cause=args.cause,
            intervention_type=args.intervention,
            date_str=args.date,
            deviation_sigma=args.deviation,
            cause_id=args.cause_id,
            intervention_id=args.intervention_id,
            subjective_rating=args.rating,
        )
        print(f"Recorded ledger entry #{row_id}")
        return 0

    if args.command == "ingest":
        row_id = ingest_session_json(Path(args.db), Path(args.json_file))
        print(f"Ingested session into ledger entry #{row_id}")
        return 0

    if args.command == "verify":
        results = verify_next_day_recovery(
            db_path=Path(args.db),
            health_db_path=Path(args.health_db),
            garmin_db_path=Path(args.garmin_db) if args.garmin_db else None,
            min_history_days=args.min_history_days,
        )
        print(json.dumps(results, indent=2))
        return 0

    if args.command == "report":
        rep = get_ledger_report(Path(args.db))
        print(json.dumps(rep, indent=2))
        return 0

    if args.command == "reflect":
        res = reflect_to_memory(Path(args.db), Path(args.memory_path))
        print("Updated MEMORY.md:")
        print(res)
        return 0

    if args.command == "recap":
        recap = generate_weekly_recap(Path(args.db))
        print(recap)
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
