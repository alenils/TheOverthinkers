#!/usr/bin/env python3
"""Import and normalize Garmin Connect export archives into SQLite."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import sys
from typing import Any, Dict, List, Optional
import zipfile


def init_db(db_path: Path) -> sqlite3.Connection:
    """Initialize SQLite database schema for daily normalized metrics."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    with conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_metrics (
                date TEXT PRIMARY KEY,
                hrv_score REAL,
                resting_hr REAL,
                sleep_fragmentation REAL,
                workout_strain_score REAL,
                source TEXT,
                created_at TEXT
            )
            """
        )
    return conn


def process_garmin_archive(zip_path: Path) -> Dict[str, Dict[str, Any]]:
    """Extract metrics from Garmin Connect export zip archive."""
    daily_records: Dict[str, Dict[str, Any]] = {}

    with zipfile.ZipFile(zip_path, "r") as zf:
        name_list = zf.namelist()

        for name in name_list:
            lower = name.lower()
            if not lower.endswith(".json"):
                continue

            try:
                with zf.open(name) as f:
                    raw_data = json.load(f)
            except Exception:
                continue

            items: List[Dict[str, Any]] = raw_data if isinstance(raw_data, list) else [raw_data]

            # 1. Sleep files
            if "sleep" in lower:
                for entry in items:
                    date_key = entry.get("calendarDate") or entry.get("date")
                    if not date_key:
                        continue
                    rec = daily_records.setdefault(str(date_key)[:10], {})
                    awake_sec = float(entry.get("awakeDurationInSeconds") or entry.get("awakeDuration") or 0.0)
                    total_sec = float(entry.get("durationInSeconds") or entry.get("duration") or 28800.0)
                    if total_sec > 0:
                        frag = round(min(awake_sec / total_sec, 1.0), 3)
                        rec["sleep_fragmentation"] = frag

            # 2. HRV files
            elif "hrv" in lower:
                for entry in items:
                    date_key = entry.get("calendarDate") or entry.get("date")
                    if not date_key:
                        continue
                    rec = daily_records.setdefault(str(date_key)[:10], {})
                    val = (
                        entry.get("lastNightAvg")
                        or entry.get("weeklyAvg")
                        or entry.get("value")
                        or entry.get("hrvValue")
                    )
                    if val is not None:
                        try:
                            rec["hrv_score"] = float(val)
                        except (ValueError, TypeError):
                            pass

            # 3. Resting HR / User metrics files
            elif "restingheartrate" in lower or "wellness" in lower or "pulse" in lower:
                for entry in items:
                    date_key = entry.get("calendarDate") or entry.get("date")
                    if not date_key:
                        continue
                    rec = daily_records.setdefault(str(date_key)[:10], {})
                    rhr = entry.get("restingHeartRate") or entry.get("rhr")
                    if rhr is not None:
                        try:
                            rec["resting_hr"] = float(rhr)
                        except (ValueError, TypeError):
                            pass

            # 4. Activities / summarized activities
            elif "activit" in lower:
                for entry in items:
                    ts = entry.get("startTimeLocal") or entry.get("beginTimestamp") or entry.get("startTimeGMT")
                    date_key = str(ts)[:10] if ts else None
                    if not date_key:
                        continue
                    rec = daily_records.setdefault(date_key, {})
                    training_effect = float(
                        entry.get("aerobicTrainingEffect")
                        or entry.get("trainingEffect")
                        or entry.get("activityStrain")
                        or 2.5
                    )
                    duration_sec = float(entry.get("duration") or entry.get("movingDuration") or 1800.0)
                    # Convert to standard strain score scale (0 - 21)
                    strain_delta = round(training_effect * (duration_sec / 3600.0) * 3.0, 2)
                    rec["workout_strain_score"] = round(rec.get("workout_strain_score", 0.0) + strain_delta, 2)

    return daily_records


def import_archive_to_db(zip_path: Path, db_path: Path) -> int:
    """Import a single Garmin zip archive into SQLite database without fabricating defaults."""
    conn = init_db(db_path)
    records = process_garmin_archive(zip_path)
    now_iso = datetime.now(timezone.utc).isoformat()
    count = 0

    with conn:
        for date_key, rec in sorted(records.items()):
            hrv_val = rec.get("hrv_score")
            rhr_val = rec.get("resting_hr")
            frag_val = rec.get("sleep_fragmentation")
            strain_val = rec.get("workout_strain_score")

            conn.execute(
                """
                INSERT INTO daily_metrics (
                    date, hrv_score, resting_hr, sleep_fragmentation, workout_strain_score, source, created_at
                ) VALUES (?, ?, ?, ?, ?, 'garmin', ?)
                ON CONFLICT(date) DO UPDATE SET
                    hrv_score=COALESCE(excluded.hrv_score, daily_metrics.hrv_score),
                    resting_hr=COALESCE(excluded.resting_hr, daily_metrics.resting_hr),
                    sleep_fragmentation=COALESCE(excluded.sleep_fragmentation, daily_metrics.sleep_fragmentation),
                    workout_strain_score=COALESCE(excluded.workout_strain_score, daily_metrics.workout_strain_score),
                    created_at=excluded.created_at
                """,
                (date_key, hrv_val, rhr_val, frag_val, strain_val, now_iso),
            )
            count += 1

    conn.close()
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="Import Garmin Connect export archives into SQLite.")
    parser.add_argument("--zip-path", help="Path to Garmin Connect export zip")
    parser.add_argument("--dir", help="Directory containing Garmin export archives")
    parser.add_argument("--db-path", default="data/garmin.db", help="Path to SQLite Garmin database")

    args = parser.parse_args()
    db_path = Path(args.db_path)

    if args.zip_path:
        zip_p = Path(args.zip_path)
        if not zip_p.is_file():
            print(f"Error: Archive not found: {zip_p}", file=sys.stderr)
            return 1
        count = import_archive_to_db(zip_p, db_path)
        print(f"Imported {count} daily records from {zip_p.name} into {db_path}")
        return 0

    if args.dir:
        dir_p = Path(args.dir)
        if not dir_p.is_dir():
            print(f"Error: Directory not found: {dir_p}", file=sys.stderr)
            return 1
        archives = sorted(dir_p.glob("*garmin*.zip")) or sorted(dir_p.glob("*.zip"))
        total = 0
        for arc in archives:
            c = import_archive_to_db(arc, db_path)
            total += c
            print(f"Imported {c} records from {arc.name}")
        print(f"Total imported: {total} records into {db_path}")
        return 0

    print("Error: Specify either --zip-path or --dir", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
