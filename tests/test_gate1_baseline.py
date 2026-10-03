"""Unit tests for Gate 1: Ingest, Rolling Baseline & Confounder Engine."""

from datetime import datetime, timedelta
import io
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import unittest
import zipfile

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "skills" / "samsung-health-import" / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "skills" / "garmin-import" / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "skills" / "detect-baseline" / "scripts"))

import baseline_math  # noqa: E402
import import_garmin  # noqa: E402
import import_samsung  # noqa: E402


class TestGate1Baseline(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_health.db"
        self.garmin_db = Path(self.temp_dir) / "test_garmin.db"

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_samsung_zip_import_no_fake_defaults(self):
        zip_path = Path(self.temp_dir) / "samsung_health_export.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            sleep_csv = (
                "start_time,end_time,duration,wake_duration\n"
                "2026-09-01 23:00:00,2026-09-02 07:00:00,480,48\n"
            )
            # Samsung stress score 30 (stress index 0-100; inverted to autonomic tone 70)
            stress_csv = (
                "start_time,score,resting_heart_rate\n"
                "2026-09-02 08:00:00,30.0,62.0\n"
            )
            zf.writestr("com.samsung.shealth.sleep_data.csv", sleep_csv)
            zf.writestr("com.samsung.shealth.stress.csv", stress_csv)

        count = import_samsung.import_archive_to_db(zip_path, self.db_path)
        self.assertEqual(count, 1)

        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM daily_metrics WHERE date = '2026-09-02'").fetchone()
        conn.close()

        self.assertIsNotNone(row)
        # Score 30 inverted to 70.0 autonomic tone
        self.assertEqual(row["hrv_score"], 70.0)
        self.assertEqual(row["resting_hr"], 62.0)
        self.assertAlmostEqual(row["sleep_fragmentation"], 0.1, places=2)
        # Workout strain was not present in zip, so it must be NULL (None), not a fabricated default
        self.assertIsNone(row["workout_strain_score"])

    def test_garmin_zip_import(self):
        zip_path = Path(self.temp_dir) / "garmin_connect_export.zip"

        sleep_json = [
            {"calendarDate": "2026-09-05", "durationInSeconds": 28800, "awakeDurationInSeconds": 1800},
            {"calendarDate": "2026-09-06", "durationInSeconds": 27000, "awakeDurationInSeconds": 2100},
        ]
        hrv_json = [
            {"calendarDate": "2026-09-05", "lastNightAvg": 56.0},
            {"calendarDate": "2026-09-06", "lastNightAvg": 54.0},
        ]
        activities_json = [
            {"startTimeLocal": "2026-09-05 16:00:00", "duration": 3600, "aerobicTrainingEffect": 3.2}
        ]

        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("DI_CONNECT/DI-Connect-Wellness/sleepData.json", json.dumps(sleep_json))
            zf.writestr("DI_CONNECT/DI-Connect-Wellness/hrvData.json", json.dumps(hrv_json))
            zf.writestr("DI_CONNECT/DI-Connect-Fitness/summarizedActivities.json", json.dumps(activities_json))

        count = import_garmin.import_archive_to_db(zip_path, self.garmin_db)
        self.assertGreaterEqual(count, 2)

        conn = sqlite3.connect(str(self.garmin_db))
        rows = conn.execute("SELECT * FROM daily_metrics ORDER BY date ASC").fetchall()
        conn.close()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][5], "garmin")

    def test_insufficient_history_guard(self):
        conn = import_samsung.init_db(self.db_path)
        base_date = datetime(2026, 9, 1)

        # Only 5 history days
        with conn:
            for day in range(5):
                d_str = (base_date + timedelta(days=day)).strftime("%Y-%m-%d")
                conn.execute(
                    "INSERT INTO daily_metrics (date, hrv_score, resting_hr, sleep_fragmentation, source) "
                    "VALUES (?, 60.0, 58.0, 0.10, 'samsung')",
                    (d_str,),
                )
            target_str = (base_date + timedelta(days=5)).strftime("%Y-%m-%d")
            conn.execute(
                "INSERT INTO daily_metrics (date, hrv_score, resting_hr, sleep_fragmentation, source) "
                "VALUES (?, 40.0, 68.0, 0.25, 'samsung')",
                (target_str,),
            )
        conn.close()

        target_rec, prior_rec, history = baseline_math.load_series_from_db(self.db_path, target_str)
        eval_res = baseline_math.evaluate_day_metrics(
            target_rec=target_rec,
            prior_rec=prior_rec,
            history_recs=history,
            min_history_days=14,
        )
        self.assertEqual(eval_res["status"], "INSUFFICIENT_HISTORY")
        self.assertFalse(eval_res["dispatch_trigger"])

    def test_unified_cross_source_merge_and_anomaly(self):
        # Samsung has sleep & stress, Garmin has workouts
        s_conn = import_samsung.init_db(self.db_path)
        g_conn = import_garmin.init_db(self.garmin_db)

        base_date = datetime(2026, 9, 1)
        with s_conn:
            for day in range(20):
                d_str = (base_date + timedelta(days=day)).strftime("%Y-%m-%d")
                s_conn.execute(
                    "INSERT INTO daily_metrics (date, hrv_score, resting_hr, sleep_fragmentation, source) "
                    "VALUES (?, ?, 58.0, 0.10, 'samsung')",
                    (d_str, 60.0 + (day % 3) - 1.0),
                )
            # Day 20: Severe autonomic drop
            target_str = (base_date + timedelta(days=20)).strftime("%Y-%m-%d")
            s_conn.execute(
                "INSERT INTO daily_metrics (date, hrv_score, resting_hr, sleep_fragmentation, source) "
                "VALUES (?, 42.0, 68.0, 0.28, 'samsung')",
                (target_str,),
            )
        s_conn.close()

        with g_conn:
            # Low workout load across all days in Garmin
            for day in range(21):
                d_str = (base_date + timedelta(days=day)).strftime("%Y-%m-%d")
                g_conn.execute(
                    "INSERT INTO daily_metrics (date, workout_strain_score, source) "
                    "VALUES (?, 3.0, 'garmin')",
                    (d_str,),
                )
        g_conn.close()

        target_rec, prior_rec, history = baseline_math.load_unified_series(
            [self.db_path, self.garmin_db], target_str, window_days=28
        )
        self.assertIsNotNone(target_rec)
        self.assertIn("samsung", target_rec["sources"])
        self.assertIn("garmin", target_rec["sources"])
        self.assertEqual(target_rec["workout_strain_score"], 3.0)

        eval_res = baseline_math.evaluate_day_metrics(
            target_rec=target_rec,
            prior_rec=prior_rec,
            history_recs=history,
            anomaly_sigma=1.5,
            workout_strain_threshold=14.0,
            min_history_days=14,
        )

        self.assertEqual(eval_res["status"], "AUTONOMIC_ANOMALY")
        self.assertTrue(eval_res["dispatch_trigger"])
        self.assertLess(eval_res["deviation_sigma"], -1.5)

    def test_workout_confounder_suppresses_mental_stress(self):
        conn = import_samsung.init_db(self.db_path)
        base_date = datetime(2026, 8, 1)

        with conn:
            for day in range(20):
                d_str = (base_date + timedelta(days=day)).strftime("%Y-%m-%d")
                conn.execute(
                    "INSERT INTO daily_metrics (date, hrv_score, resting_hr, sleep_fragmentation, workout_strain_score, source) "
                    "VALUES (?, ?, 60.0, 0.12, 4.0, 'samsung')",
                    (d_str, 58.0 + (day % 3) - 1.0),
                )

            # Prior day (Day 19) had an intense workout strain of 18.0
            prior_dt = base_date + timedelta(days=19)
            conn.execute(
                "UPDATE daily_metrics SET workout_strain_score = 18.5 WHERE date = ?",
                (prior_dt.strftime("%Y-%m-%d"),),
            )

            # Target day (Day 20): Severe autonomic dip
            target_dt = base_date + timedelta(days=20)
            target_str = target_dt.strftime("%Y-%m-%d")
            conn.execute(
                "INSERT INTO daily_metrics (date, hrv_score, resting_hr, sleep_fragmentation, workout_strain_score, source) "
                "VALUES (?, 40.0, 66.0, 0.25, 2.0, 'samsung')",
                (target_str,),
            )
        conn.close()

        target_rec, prior_rec, history = baseline_math.load_series_from_db(self.db_path, target_str, window_days=28)
        eval_res = baseline_math.evaluate_day_metrics(
            target_rec=target_rec,
            prior_rec=prior_rec,
            history_recs=history,
            anomaly_sigma=1.5,
            workout_strain_threshold=14.0,
            min_history_days=14,
        )

        self.assertEqual(eval_res["status"], "PHYSICAL_RECOVERY_STRAIN")
        self.assertFalse(eval_res["dispatch_trigger"])
        self.assertIn("athletic load", eval_res["message"].lower())

    def test_zero_variance_history_rejected(self):
        conn = import_samsung.init_db(self.db_path)
        base_date = datetime(2026, 7, 1)

        with conn:
            for day in range(20):
                d_str = (base_date + timedelta(days=day)).strftime("%Y-%m-%d")
                # Exactly identical flatline
                conn.execute(
                    "INSERT INTO daily_metrics (date, hrv_score, resting_hr, sleep_fragmentation, workout_strain_score, source) "
                    "VALUES (?, 55.0, 60.0, 0.10, 4.0, 'samsung')",
                    (d_str,),
                )
            target_str = (base_date + timedelta(days=20)).strftime("%Y-%m-%d")
            conn.execute(
                "INSERT INTO daily_metrics (date, hrv_score, resting_hr, sleep_fragmentation, workout_strain_score, source) "
                "VALUES (?, 40.0, 65.0, 0.25, 4.0, 'samsung')",
                (target_str,),
            )
        conn.close()

        target_rec, prior_rec, history = baseline_math.load_series_from_db(self.db_path, target_str, window_days=28)
        eval_res = baseline_math.evaluate_day_metrics(
            target_rec=target_rec,
            prior_rec=prior_rec,
            history_recs=history,
            min_history_days=14,
        )
        self.assertEqual(eval_res["status"], "ZERO_VARIANCE_INSUFFICIENT_DATA")
        self.assertFalse(eval_res["dispatch_trigger"])

    def test_missing_workout_strain_unverified(self):
        conn = import_samsung.init_db(self.db_path)
        base_date = datetime(2026, 6, 1)

        with conn:
            for day in range(20):
                d_str = (base_date + timedelta(days=day)).strftime("%Y-%m-%d")
                conn.execute(
                    "INSERT INTO daily_metrics (date, hrv_score, resting_hr, sleep_fragmentation, source) "
                    "VALUES (?, ?, 60.0, 0.10, 'samsung')",
                    (d_str, 58.0 + (day % 3) - 1.0),
                )
            target_str = (base_date + timedelta(days=20)).strftime("%Y-%m-%d")
            # Target day has dip, but prior day had NULL workout strain
            conn.execute(
                "INSERT INTO daily_metrics (date, hrv_score, resting_hr, sleep_fragmentation, source) "
                "VALUES (?, 40.0, 66.0, 0.25, 'samsung')",
                (target_str,),
            )
        conn.close()

        target_rec, prior_rec, history = baseline_math.load_series_from_db(self.db_path, target_str, window_days=28)
        eval_res = baseline_math.evaluate_day_metrics(
            target_rec=target_rec,
            prior_rec=prior_rec,
            history_recs=history,
            min_history_days=14,
        )
        # Must not crash, and must report unverified missing workout data
        self.assertEqual(eval_res["status"], "AUTONOMIC_ANOMALY")
        self.assertEqual(eval_res["confounder_status"], "WORKOUT_DATA_MISSING_UNVERIFIED")


if __name__ == "__main__":
    unittest.main()
