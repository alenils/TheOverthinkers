#!/usr/bin/env python3
"""Rolling baseline computation and athletic workout confounder filter.

Detects individual slope breaks (mu +- 1.5 sigma) on nightly autonomic tone
and sleep fragmentation, suppressing mental stress check-ins when prior-day
athletic workout strain explains the physiological dip, and returning explicit
insufficient-data states when baseline variance is zero or workout data is missing.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import re
import sqlite3
import sys
from typing import Any, Dict, List, Optional, Tuple


def compute_mean_and_std(values: List[float]) -> Tuple[float, float]:
    """Compute arithmetic mean and sample standard deviation."""
    if not values:
        return 0.0, 0.0
    n = len(values)
    mean = sum(values) / n
    if n < 2:
        return mean, 0.0
    variance = sum((x - mean) ** 2 for x in values) / (n - 1)
    return mean, math.sqrt(max(variance, 0.0))


def compute_z_score(val: float, mean: float, std: float) -> float:
    """Calculate z-score; return 0.0 if standard deviation has zero/near-zero variance."""
    if std <= 1e-4:
        return 0.0
    return (val - mean) / std


def check_slope_break(
    current_val: float,
    history: List[float],
    metric_name: str,
    threshold_sigma: float = 1.5,
    prior_val: Optional[float] = None,
) -> Tuple[bool, float, float, float, Optional[float]]:
    """Check whether current_val represents an anomalous slope break.

    Calculates:
      1. Level z-score against historical baseline mean & std.
      2. Trajectory slope break (step-change discontinuity vs historical daily deltas).
    """
    mean, std = compute_mean_and_std(history)
    if std <= 1e-4:
        return False, 0.0, mean, std, None

    z = compute_z_score(current_val, mean, std)

    # Compute rate-of-change delta slope if prior value exists
    slope_delta = None
    is_slope_anomaly = False
    if prior_val is not None:
        daily_deltas = [history[i] - history[i - 1] for i in range(1, len(history))]
        if daily_deltas:
            mean_delta, std_delta = compute_mean_and_std(daily_deltas)
            if std_delta > 1e-4:
                current_delta = current_val - prior_val
                z_delta = compute_z_score(current_delta, mean_delta, std_delta)
                slope_delta = z_delta
                if metric_name == "hrv_score" and z_delta <= -threshold_sigma:
                    is_slope_anomaly = True
                elif metric_name == "sleep_fragmentation" and z_delta >= threshold_sigma:
                    is_slope_anomaly = True

    if metric_name == "hrv_score":
        is_level_break = z <= -threshold_sigma
    elif metric_name == "sleep_fragmentation":
        is_level_break = z >= threshold_sigma
    else:
        is_level_break = abs(z) >= threshold_sigma

    is_break = is_level_break or is_slope_anomaly
    return is_break, z, mean, std, slope_delta


def evaluate_workout_confounder(
    prior_strain: Optional[float],
    historical_strains: List[float],
    absolute_threshold: float = 14.0,
    strain_sigma_threshold: float = 1.5,
) -> Tuple[str, str]:
    """Determine whether prior day's workout strain explains the physiological dip.

    Returns:
      (status, reason_message)
      status: "CONFOUNDED_STRAIN" | "NO_CONFOUNDER_DETECTED" | "WORKOUT_DATA_MISSING_UNVERIFIED"
    """
    if prior_strain is None:
        return (
            "WORKOUT_DATA_MISSING_UNVERIFIED",
            "No prior-day workout records available; athletic exertion cannot be verified or ruled out.",
        )

    if prior_strain >= absolute_threshold:
        return (
            "CONFOUNDED_STRAIN",
            f"Absolute workout strain score {prior_strain:.1f} >= threshold {absolute_threshold:.1f}",
        )

    if historical_strains:
        mean_strain, std_strain = compute_mean_and_std(historical_strains)
        z_strain = compute_z_score(prior_strain, mean_strain, std_strain)
        if z_strain is not None and z_strain >= strain_sigma_threshold:
            return (
                "CONFOUNDED_STRAIN",
                f"Workout strain jump z={z_strain:.2f} >= {strain_sigma_threshold:.1f} sigma above training baseline",
            )

    return (
        "NO_CONFOUNDER_DETECTED",
        f"Prior day athletic strain ({prior_strain:.1f}) within normal training variance.",
    )


def load_series_from_db(
    db_path: Path,
    target_date: str,
    window_days: int = 28,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    """Load target day, prior day, and history window from a single SQLite daily_metrics table."""
    return load_unified_series([db_path], target_date, window_days=window_days)


def load_unified_series(
    db_paths: List[Path],
    target_date: str,
    window_days: int = 28,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    """Unified query layer: loads and merges records across multiple wearable DBs while tracking source provenance."""
    dt_target = datetime.strptime(target_date, "%Y-%m-%d")
    dt_prior = dt_target - timedelta(days=1)
    prior_date = dt_prior.strftime("%Y-%m-%d")

    dt_start = dt_target - timedelta(days=window_days)
    start_date = dt_start.strftime("%Y-%m-%d")

    merged_by_date: Dict[str, Dict[str, Any]] = {}

    for db_p in db_paths:
        if not db_p.is_file():
            continue

        conn = sqlite3.connect(str(db_p))
        conn.row_factory = sqlite3.Row
        with conn:
            rows = conn.execute(
                """
                SELECT date, hrv_score, resting_hr, sleep_fragmentation, workout_strain_score, source
                FROM daily_metrics
                WHERE date >= ? AND date <= ?
                ORDER BY date ASC
                """,
                (start_date, target_date),
            ).fetchall()
        conn.close()

        for r in rows:
            d = r["date"]
            cur = merged_by_date.setdefault(d, {
                "date": d,
                "hrv_score": None,
                "resting_hr": None,
                "sleep_fragmentation": None,
                "workout_strain_score": None,
                "sources": [],
                "metric_sources": {},
            })
            src = r["source"] or "wearable"
            if src not in cur["sources"]:
                cur["sources"].append(src)

            if r["hrv_score"] is not None and cur["hrv_score"] is None:
                cur["hrv_score"] = float(r["hrv_score"])
                cur["metric_sources"]["hrv_score"] = src
            if r["resting_hr"] is not None and cur["resting_hr"] is None:
                cur["resting_hr"] = float(r["resting_hr"])
                cur["metric_sources"]["resting_hr"] = src
            if r["sleep_fragmentation"] is not None and cur["sleep_fragmentation"] is None:
                cur["sleep_fragmentation"] = float(r["sleep_fragmentation"])
                cur["metric_sources"]["sleep_fragmentation"] = src
            if r["workout_strain_score"] is not None:
                existing_strain = cur["workout_strain_score"] or 0.0
                val = float(r["workout_strain_score"])
                if val >= existing_strain:
                    cur["workout_strain_score"] = val
                    cur["metric_sources"]["workout_strain_score"] = src

    target_rec = merged_by_date.get(target_date)
    prior_rec = merged_by_date.get(prior_date)
    history_recs = [merged_by_date[d] for d in sorted(merged_by_date.keys()) if d < target_date]

    return target_rec, prior_rec, history_recs


def check_quiet_hours(dt: datetime, quiet_hours: str = "08:00-21:00") -> bool:
    """Return True if dt time is within the allowed proactive ping window."""
    m = re.match(r"^(\d{2}):(\d{2})-(\d{2}):(\d{2})$", quiet_hours.strip())
    if not m:
        return True
    start_h, start_m, end_h, end_m = map(int, m.groups())
    t = dt.time()
    start_time = datetime.min.time().replace(hour=start_h, minute=start_m)
    end_time = datetime.min.time().replace(hour=end_h, minute=end_m)
    if start_time <= end_time:
        return start_time <= t <= end_time
    return t >= start_time or t <= end_time


def evaluate_day_metrics(
    target_rec: Dict[str, Any],
    prior_rec: Optional[Dict[str, Any]],
    history_recs: List[Dict[str, Any]],
    anomaly_sigma: float = 1.5,
    workout_strain_threshold: float = 14.0,
    min_history_days: int = 14,
) -> Dict[str, Any]:
    """Run rolling baseline evaluation and workout confounder interlock with explicit data-quality guards."""
    target_date = target_rec["date"]

    # Filter history records having valid autonomic values
    valid_hrv_history = [
        float(r["hrv_score"]) for r in history_recs if r.get("hrv_score") is not None
    ]
    valid_frag_history = [
        float(r["sleep_fragmentation"]) for r in history_recs if r.get("sleep_fragmentation") is not None
    ]

    if len(valid_hrv_history) < min_history_days and len(valid_frag_history) < min_history_days:
        return {
            "date": target_date,
            "status": "INSUFFICIENT_HISTORY",
            "message": f"Requires at least {min_history_days} baseline history days; found {len(valid_hrv_history)}",
            "dispatch_trigger": False,
        }

    # Check if baseline completely lacks variance across all metrics
    _, hrv_std_check = compute_mean_and_std(valid_hrv_history) if valid_hrv_history else (0.0, 0.0)
    _, frag_std_check = compute_mean_and_std(valid_frag_history) if valid_frag_history else (0.0, 0.0)
    if hrv_std_check <= 1e-4 and frag_std_check <= 1e-4:
        return {
            "date": target_date,
            "status": "ZERO_VARIANCE_INSUFFICIENT_DATA",
            "message": "Baseline history lacks physiological variance (std <= 1e-4); cannot compute slope break.",
            "dispatch_trigger": False,
        }

    # Background training strain history strictly precedes prior day (no self-normalization)
    prior_date_str = (datetime.strptime(target_date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    background_strain_history = [
        float(r["workout_strain_score"])
        for r in history_recs
        if r.get("workout_strain_score") is not None and r["date"] < prior_date_str
    ]

    current_hrv = target_rec.get("hrv_score")
    current_frag = target_rec.get("sleep_fragmentation")

    # Safely extract prior day strain without crashing on None
    prior_strain: Optional[float] = None
    if prior_rec and prior_rec.get("workout_strain_score") is not None:
        prior_strain = float(prior_rec["workout_strain_score"])

    # Extract prior day hrv/frag for slope delta calculation
    prior_hrv = float(prior_rec["hrv_score"]) if (prior_rec and prior_rec.get("hrv_score") is not None) else None
    prior_frag = float(prior_rec["sleep_fragmentation"]) if (prior_rec and prior_rec.get("sleep_fragmentation") is not None) else None

    hrv_break = False
    hrv_z, hrv_mean, hrv_std, hrv_slope_z = 0.0, 0.0, 0.0, None
    if current_hrv is not None and len(valid_hrv_history) >= min_history_days:
        hrv_break, hrv_z, hrv_mean, hrv_std, hrv_slope_z = check_slope_break(
            float(current_hrv), valid_hrv_history, "hrv_score", anomaly_sigma, prior_val=prior_hrv
        )

    frag_break = False
    frag_z, frag_mean, frag_std, frag_slope_z = 0.0, 0.0, 0.0, None
    if current_frag is not None and len(valid_frag_history) >= min_history_days:
        frag_break, frag_z, frag_mean, frag_std, frag_slope_z = check_slope_break(
            float(current_frag), valid_frag_history, "sleep_fragmentation", anomaly_sigma, prior_val=prior_frag
        )

    is_anomaly = hrv_break or frag_break
    triggered_metric = "hrv_score" if hrv_break else ("sleep_fragmentation" if frag_break else "none")
    deviation_val = hrv_z if hrv_break else (frag_z if frag_break else 0.0)

    # Confounder check
    confounder_status, confounder_reason = evaluate_workout_confounder(
        prior_strain, background_strain_history, workout_strain_threshold, anomaly_sigma
    )

    if not is_anomaly:
        return {
            "date": target_date,
            "status": "BASELINE_NORMAL",
            "dispatch_trigger": False,
            "hrv": {"value": current_hrv, "mean": round(hrv_mean, 2), "z_score": round(hrv_z, 2)},
            "sleep_fragmentation": {"value": current_frag, "mean": round(frag_mean, 2), "z_score": round(frag_z, 2)},
            "message": "Metrics within personal rolling baseline variance. Silence.",
        }

    if confounder_status == "CONFOUNDED_STRAIN":
        return {
            "date": target_date,
            "status": "PHYSICAL_RECOVERY_STRAIN",
            "dispatch_trigger": False,
            "suppressed_metric": triggered_metric,
            "deviation_sigma": round(deviation_val, 2),
            "prior_workout_strain": prior_strain,
            "confounder_status": confounder_status,
            "confounder_reason": confounder_reason,
            "message": f"Autonomic dip on {triggered_metric} explained by athletic load. Suppressed mental stress check-in. Silence.",
        }

    if confounder_status == "WORKOUT_DATA_MISSING_UNVERIFIED":
        # Dispatches with unverified confounder warning so downstream coach and ledger are aware
        return {
            "date": target_date,
            "status": "AUTONOMIC_ANOMALY",
            "dispatch_trigger": True,
            "triggered_metric": triggered_metric,
            "deviation_sigma": round(deviation_val, 2),
            "hrv": {"value": current_hrv, "mean": round(hrv_mean, 2), "z_score": round(hrv_z, 2)},
            "sleep_fragmentation": {"value": current_frag, "mean": round(frag_mean, 2), "z_score": round(frag_z, 2)},
            "prior_workout_strain": None,
            "confounder_status": "WORKOUT_DATA_MISSING_UNVERIFIED",
            "confounder_reason": confounder_reason,
            "metric_sources": target_rec.get("metric_sources", {}),
            "message": f"Slope break confirmed on {triggered_metric} (z={deviation_val:.2f}), but prior workout records are missing.",
        }

    # Authentic unconfounded psychological / autonomic anomaly
    return {
        "date": target_date,
        "status": "AUTONOMIC_ANOMALY",
        "dispatch_trigger": True,
        "triggered_metric": triggered_metric,
        "deviation_sigma": round(deviation_val, 2),
        "hrv": {"value": current_hrv, "mean": round(hrv_mean, 2), "z_score": round(hrv_z, 2)},
        "sleep_fragmentation": {"value": current_frag, "mean": round(frag_mean, 2), "z_score": round(frag_z, 2)},
        "prior_workout_strain": prior_strain,
        "confounder_status": "NO_CONFOUNDER_DETECTED",
        "confounder_reason": confounder_reason,
        "metric_sources": target_rec.get("metric_sources", {}),
        "message": f"Slope break confirmed on {triggered_metric} (z={deviation_val:.2f}). Ready for cognitive appraisal.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate rolling baseline and workout confounders.")
    subparsers = parser.add_subparsers(dest="command")

    check_p = subparsers.add_parser("check", help="Check baseline for a given date in DB")
    check_p.add_argument("--date", required=True, help="Target date YYYY-MM-DD")
    check_p.add_argument("--db-path", default="data/health.db", help="Path to primary SQLite metrics database")
    check_p.add_argument("--garmin-db", default="data/garmin.db", help="Path to secondary Garmin SQLite database")
    check_p.add_argument("--window-days", type=int, default=28, help="Rolling window size in days")
    check_p.add_argument("--min-history-days", type=int, default=14, help="Minimum history days required")
    check_p.add_argument("--anomaly-sigma", type=float, default=1.5, help="Anomaly sigma threshold")
    check_p.add_argument("--strain-threshold", type=float, default=14.0, help="Workout strain threshold")

    args = parser.parse_args()

    if args.command == "check":
        db_paths = [Path(args.db_path)]
        if args.garmin_db:
            g_path = Path(args.garmin_db)
            if g_path.is_file() and g_path not in db_paths:
                db_paths.append(g_path)

        try:
            target_rec, prior_rec, history_recs = load_unified_series(
                db_paths, args.date, window_days=args.window_days
            )
        except Exception as e:
            print(json.dumps({"error": str(e)}, indent=2))
            return 1

        if not target_rec:
            print(json.dumps({"error": f"No record found for date {args.date}"}, indent=2))
            return 1

        res = evaluate_day_metrics(
            target_rec=target_rec,
            prior_rec=prior_rec,
            history_recs=history_recs,
            anomaly_sigma=args.anomaly_sigma,
            workout_strain_threshold=args.strain_threshold,
            min_history_days=args.min_history_days,
        )
        print(json.dumps(res, indent=2))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
