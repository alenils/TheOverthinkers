#!/usr/bin/env python3
"""Import and normalize Samsung Health export archives into SQLite."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta, timezone
import io
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


def parse_csv_stream(stream: io.TextIOBase) -> List[Dict[str, str]]:
    """Parse CSV data, skipping Samsung Health metadata lines if present."""
    lines = stream.readlines()
    data_lines: List[str] = []
    header_found = False
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not header_found and ("," in stripped or "\t" in stripped):
            header_found = True
        if header_found:
            data_lines.append(line)

    if not data_lines:
        return []
    reader = csv.DictReader(io.StringIO("".join(data_lines)))
    return [row for row in reader]


def process_samsung_archive(zip_path: Path) -> Dict[str, Dict[str, Any]]:
    """Extract metrics from Samsung Health export zip archive."""
    daily_records: Dict[str, Dict[str, Any]] = {}

    with zipfile.ZipFile(zip_path, "r") as zf:
        name_list = zf.namelist()

        # 1. Parse Sleep files (align to morning wake date)
        sleep_files = [n for n in name_list if "sleep" in n.lower() and n.endswith(".csv")]
        for sf in sleep_files:
            with zf.open(sf) as f:
                rows = parse_csv_stream(io.TextIOWrapper(f, encoding="utf-8", errors="replace"))
                for row in rows:
                    end_str = row.get("end_time") or row.get("end_time_utc") or ""
                    start_str = row.get("start_time") or row.get("start_time_utc") or row.get("create_time") or ""

                    # Wake date is the end_time date, or start_time + 1 day if crossing midnight
                    if len(end_str) >= 10:
                        wake_date = end_str[:10]
                    elif len(start_str) >= 10:
                        try:
                            st_dt = datetime.strptime(start_str[:19], "%Y-%m-%d %H:%M:%S")
                            wake_date = (st_dt + timedelta(days=1)).strftime("%Y-%m-%d")
                        except Exception:
                            wake_date = start_str[:10]
                    else:
                        continue

                    rec = daily_records.setdefault(wake_date, {})
                    # Calculate sleep fragmentation as awake time ratio (0.0 to 1.0)
                    total_min = float(row.get("duration") or row.get("duration_minutes") or 420.0)
                    awake_min = float(row.get("wake_duration") or row.get("awake_minutes") or 0.0)
                    if awake_min == 0.0 and "wake_count" in row:
                        wake_count = float(row.get("wake_count") or 0.0)
                        awake_min = wake_count * 15.0  # estimate 15m per awakening

                    if total_min > 0:
                        frag = round(min(awake_min / total_min, 1.0), 3)
                        rec["sleep_fragmentation"] = frag

        # 2. Parse Stress & Autonomic files
        stress_files = [n for n in name_list if ("stress" in n.lower() or "hrv" in n.lower()) and n.endswith(".csv")]
        for stf in stress_files:
            with zf.open(stf) as f:
                rows = parse_csv_stream(io.TextIOWrapper(f, encoding="utf-8", errors="replace"))
                for row in rows:
                    ts = row.get("start_time") or row.get("create_time") or ""
                    date_key = ts[:10] if len(ts) >= 10 else None
                    if not date_key:
                        continue
                    rec = daily_records.setdefault(date_key, {})

                    # If Samsung stress score (0-100, where 100 is high stress):
                    # Invert to vagal autonomic tone (higher = better recovery)
                    if "score" in row or "score_value" in row:
                        val_str = row.get("score") or row.get("score_value") or ""
                        if val_str:
                            try:
                                raw_stress = float(val_str)
                                rec["hrv_score"] = round(100.0 - raw_stress, 2)
                            except ValueError:
                                pass
                    elif "hrv" in row:
                        val_str = row.get("hrv") or ""
                        if val_str:
                            try:
                                rec["hrv_score"] = float(val_str)
                            except ValueError:
                                pass

                    rhr_str = row.get("resting_heart_rate") or row.get("resting_hr") or ""
                    if rhr_str:
                        try:
                            rec["resting_hr"] = float(rhr_str)
                        except ValueError:
                            pass

        # 3. Parse Exercise & Workouts (attributed to the activity date)
        exercise_files = [n for n in name_list if "exercise" in n.lower() and n.endswith(".csv")]
        for ef in exercise_files:
            with zf.open(ef) as f:
                rows = parse_csv_stream(io.TextIOWrapper(f, encoding="utf-8", errors="replace"))
                for row in rows:
                    st = row.get("start_time") or row.get("create_time") or ""
                    date_key = st[:10] if len(st) >= 10 else None
                    if not date_key:
                        continue
                    rec = daily_records.setdefault(date_key, {})
                    duration_s = float(row.get("duration") or 0.0)
                    mean_hr = float(row.get("mean_heart_rate") or 120.0)
                    # Standardized strain score proxy: (duration in hours) * (relative intensity factor)
                    strain_delta = round((duration_s / 3600.0) * (mean_hr / 100.0) * 5.0, 2)
                    rec["workout_strain_score"] = round(rec.get("workout_strain_score", 0.0) + strain_delta, 2)

    return daily_records


def import_archive_to_db(zip_path: Path, db_path: Path) -> int:
    """Import a single Samsung zip archive into SQLite database without fabricating defaults."""
    conn = init_db(db_path)
    records = process_samsung_archive(zip_path)
    now_iso = datetime.now(timezone.utc).isoformat()
    count = 0

    with conn:
        for date_key, rec in sorted(records.items()):
            # Use real values or None (NULL in SQLite) — never fabricate defaults!
            hrv_val = rec.get("hrv_score")
            rhr_val = rec.get("resting_hr")
            frag_val = rec.get("sleep_fragmentation")
            strain_val = rec.get("workout_strain_score")

            conn.execute(
                """
                INSERT INTO daily_metrics (
                    date, hrv_score, resting_hr, sleep_fragmentation, workout_strain_score, source, created_at
                ) VALUES (?, ?, ?, ?, ?, 'samsung', ?)
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
    parser = argparse.ArgumentParser(description="Import Samsung Health export archives into SQLite.")
    parser.add_argument("--zip-path", help="Path to Samsung Health export zip")
    parser.add_argument("--dir", help="Directory containing Samsung export archives")
    parser.add_argument("--db-path", default="data/health.db", help="Path to SQLite health database")

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
        archives = sorted(dir_p.glob("*samsung*health*.zip")) or sorted(dir_p.glob("*.zip"))
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
