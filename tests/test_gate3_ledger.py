"""Unit tests for Gate 3: Closed-Loop Outcome Ledger & Personal Adaptation."""

from datetime import datetime, timedelta
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "skills" / "stress-ledger" / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "skills" / "samsung-health-import" / "scripts"))

import import_samsung  # noqa: E402
import ledger  # noqa: E402
import orchestrator  # noqa: E402


class TestGate3Ledger(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.ledger_db = Path(self.temp_dir) / "test_ledger.db"
        self.health_db = Path(self.temp_dir) / "test_health.db"
        self.memory_file = Path(self.temp_dir) / "MEMORY.md"

        # Seed memory file with authentic dividers and standing rules
        seed_memory = (
            "# Tier 3: Living Memory & Efficacy Ledger (`MEMORY.md`)\n\n"
            "---\n\n"
            "## Active Stressors\n\n"
            "* High-bandwidth project delivery.\n\n"
            "---\n\n"
            "## Intervention Efficacy Ledger (Unverified Baseline Seeds — Pending Gate 3 Verification)\n\n"
            "* Placeholder seeds.\n\n"
            "---\n\n"
            "## Standing Rules & Interaction Preferences\n\n"
            "* Strictly bound check-ins to <= 3 turns.\n"
        )
        self.memory_file.write_text(seed_memory, encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_add_and_ingest_session(self):
        entry_id = ledger.add_ledger_entry(
            db_path=self.ledger_db,
            trigger_metric="hrv_score",
            attributed_cause="Work deadline sprint",
            intervention_type="Physiological sigh (3 cycles)",
            date_str="2026-10-01",
            deviation_sigma=-1.8,
            cause_id="CHALLENGE_LOAD",
            intervention_id="PHYSIOLOGICAL_SIGH",
            subjective_rating=7,
        )
        self.assertEqual(entry_id, 1)

        # Ingest session summary JSON
        session_json_path = Path(self.temp_dir) / "session.json"
        session_data = {
            "date": "2026-10-02",
            "trigger_metric": "hrv_score",
            "deviation_sigma": -2.0,
            "attributed_cause": "Conflict in review meeting",
            "cause_id": "ACUTE_THREAT",
            "intervention_type": "15-minute outdoor walk",
            "intervention_id": "OUTDOOR_WALK",
            "subjective_rating": 8,
        }
        session_json_path.write_text(json.dumps(session_data), encoding="utf-8")

        ingest_id = ledger.ingest_session_json(self.ledger_db, session_json_path)
        self.assertEqual(ingest_id, 2)

        report = ledger.get_ledger_report(self.ledger_db)
        self.assertEqual(report["total_entries"], 2)
        self.assertEqual(report["verified_entries"], 0)

    def test_verify_next_day_hrv_rebound(self):
        checkin_date = "2026-09-15"
        ledger.add_ledger_entry(
            db_path=self.ledger_db,
            trigger_metric="hrv_score",
            attributed_cause="Deadline pressure",
            intervention_type="Physiological sigh",
            date_str=checkin_date,
            deviation_sigma=-1.8,
            cause_id="CHALLENGE_LOAD",
            intervention_id="PHYSIOLOGICAL_SIGH",
            subjective_rating=8,
        )

        conn = import_samsung.init_db(self.health_db)
        base_date = datetime(2026, 8, 20)
        with conn:
            for day in range(25):
                cur_dt = base_date + timedelta(days=day)
                d_str = cur_dt.strftime("%Y-%m-%d")
                conn.execute(
                    "INSERT OR REPLACE INTO daily_metrics (date, hrv_score, resting_hr, sleep_fragmentation, workout_strain_score, source) "
                    "VALUES (?, ?, 58.0, 0.10, 3.0, 'samsung')",
                    (d_str, 60.0 + (day % 3) - 1.0),
                )
            # Check-in day (2026-09-15): autonomic dip
            conn.execute(
                "INSERT OR REPLACE INTO daily_metrics (date, hrv_score, resting_hr, sleep_fragmentation, workout_strain_score, source) "
                "VALUES ('2026-09-15', 42.0, 68.0, 0.28, 2.0, 'samsung')"
            )
            # Subsequent night (2026-09-16): Rebound to 61.0 (mean ~60)
            conn.execute(
                "INSERT OR REPLACE INTO daily_metrics (date, hrv_score, resting_hr, sleep_fragmentation, workout_strain_score, source) "
                "VALUES ('2026-09-16', 61.0, 59.0, 0.11, 3.0, 'samsung')"
            )
        conn.close()

        results = ledger.verify_next_day_recovery(
            db_path=self.ledger_db,
            health_db_path=self.health_db,
            min_history_days=14,
        )
        self.assertEqual(len(results), 1)
        res = results[0]
        self.assertEqual(res["date"], checkin_date)
        self.assertEqual(res["next_day_date"], "2026-09-16")
        self.assertEqual(res["status"], "REBOUND_CONFIRMED")
        self.assertGreater(res["rebound_delta"], 1.0)

    def test_verify_stale_entry_expires(self):
        # Entry from 30 days ago with no subsequent data should expire instead of staying pending
        stale_date = "2026-08-01"
        ledger.add_ledger_entry(
            db_path=self.ledger_db,
            trigger_metric="hrv_score",
            attributed_cause="Old stressor",
            intervention_type="Physiological sigh",
            date_str=stale_date,
            deviation_sigma=-1.8,
        )
        empty_health_db = Path(self.temp_dir) / "empty_health.db"
        import_samsung.init_db(empty_health_db)

        results = ledger.verify_next_day_recovery(
            db_path=self.ledger_db,
            health_db_path=empty_health_db,
        )
        self.assertEqual(len(results), 0)

        conn = ledger.init_ledger_db(self.ledger_db)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM stress_ledger WHERE date = ?", (stale_date,)).fetchone()
        conn.close()
        self.assertEqual(row["rebound_status"], "EXPIRED_NO_DATA")

    def test_verify_sleep_fragmentation_rebound_directionality(self):
        checkin_date = "2026-09-15"
        # Sleep fragmentation spiked to +2.0 sigma
        ledger.add_ledger_entry(
            db_path=self.ledger_db,
            trigger_metric="sleep_fragmentation",
            attributed_cause="Evening rumination loop",
            intervention_type="Screen curfew",
            date_str=checkin_date,
            deviation_sigma=2.0,
            cause_id="RECOVERY_DEFICIT",
            intervention_id="SCREEN_CURFEW",
            metric_source="samsung",
            baseline_mean=0.10,
            baseline_std=0.02,
        )

        conn = import_samsung.init_db(self.health_db)
        base_date = datetime(2026, 8, 20)
        with conn:
            for day in range(25):
                cur_dt = base_date + timedelta(days=day)
                d_str = cur_dt.strftime("%Y-%m-%d")
                conn.execute(
                    "INSERT OR REPLACE INTO daily_metrics (date, hrv_score, resting_hr, sleep_fragmentation, workout_strain_score, source) "
                    "VALUES (?, 60.0, 58.0, 0.10, 3.0, 'samsung')",
                    (d_str,),
                )
            # Checkin day: fragmentation spiked to 0.35
            conn.execute(
                "INSERT OR REPLACE INTO daily_metrics (date, hrv_score, resting_hr, sleep_fragmentation, workout_strain_score, source) "
                "VALUES ('2026-09-15', 58.0, 60.0, 0.35, 2.0, 'samsung')"
            )
            # Subsequent night: normalized back down to 0.09
            conn.execute(
                "INSERT OR REPLACE INTO daily_metrics (date, hrv_score, resting_hr, sleep_fragmentation, workout_strain_score, source) "
                "VALUES ('2026-09-16', 60.0, 58.0, 0.09, 3.0, 'samsung')"
            )
        conn.close()

        results = ledger.verify_next_day_recovery(
            db_path=self.ledger_db,
            health_db_path=self.health_db,
            min_history_days=14,
        )
        self.assertEqual(len(results), 1)
        res = results[0]
        # For fragmentation, dropping from 2.0 to <= 1.0 is REBOUND_CONFIRMED!
        self.assertEqual(res["status"], "REBOUND_CONFIRMED")
        self.assertGreater(res["rebound_delta"], 0.0)

    def test_reflect_preserves_dividers_and_standing_rules(self):
        conn = ledger.init_ledger_db(self.ledger_db)
        with conn:
            conn.execute(
                """
                INSERT INTO stress_ledger (
                    date, trigger_metric, deviation_sigma, attributed_cause, cause_id,
                    intervention_type, intervention_id, subjective_rating,
                    next_day_date, next_day_metric_val, next_day_sigma, next_day_rebound_delta,
                    rebound_status, created_at, verified_at
                ) VALUES
                ('2026-09-10', 'hrv_score', -1.9, 'Work sprint', 'CHALLENGE_LOAD',
                 'Physiological Sigh', 'PHYSIOLOGICAL_SIGH', 9,
                 '2026-09-11', 62.0, 0.2, 2.1, 'REBOUND_CONFIRMED', '2026-09-10', '2026-09-11')
                """
            )
        conn.close()

        ledger.reflect_to_memory(self.ledger_db, self.memory_file)
        updated = self.memory_file.read_text(encoding="utf-8")

        self.assertIn("## Intervention Follow-Up Ledger", updated)
        self.assertIn("Physiological Sigh (3 cycles)", updated)
        # Dividers and standing rules MUST be preserved!
        self.assertIn("---\n\n## Standing Rules & Interaction Preferences", updated)
        self.assertIn("Strictly bound check-ins to <= 3 turns.", updated)

    def test_end_to_end_orchestrator_pipeline(self):
        # 1. Populate 20 baseline days in health DB
        conn = import_samsung.init_db(self.health_db)
        base_date = datetime(2026, 9, 1)
        with conn:
            for day in range(20):
                d_str = (base_date + timedelta(days=day)).strftime("%Y-%m-%d")
                conn.execute(
                    "INSERT INTO daily_metrics (date, hrv_score, resting_hr, sleep_fragmentation, workout_strain_score, source) "
                    "VALUES (?, ?, 58.0, 0.10, 3.0, 'samsung')",
                    (d_str, 60.0 + (day % 3) - 1.0),
                )
            # Day 20: Anomaly day (2026-09-21)
            target_str = (base_date + timedelta(days=20)).strftime("%Y-%m-%d")
            conn.execute(
                "INSERT INTO daily_metrics (date, hrv_score, resting_hr, sleep_fragmentation, workout_strain_score, source) "
                "VALUES (?, 42.0, 68.0, 0.28, 2.0, 'samsung')",
                (target_str,),
            )
            # Day 21: Subsequent recovery day (2026-09-22)
            next_str = (base_date + timedelta(days=21)).strftime("%Y-%m-%d")
            conn.execute(
                "INSERT INTO daily_metrics (date, hrv_score, resting_hr, sleep_fragmentation, workout_strain_score, source) "
                "VALUES (?, 61.0, 58.0, 0.10, 3.0, 'samsung')",
                (next_str,),
            )
        conn.close()

        state_file = Path(self.temp_dir) / "state.json"

        # Run day 20: Anomaly detected -> Dialogue runs -> Ledger records entry
        rep_day20 = orchestrator.run_pipeline(
            target_date=target_str,
            health_db=self.health_db,
            ledger_db=self.ledger_db,
            memory_path=self.memory_file,
            state_file=state_file,
            mock_reply="Launching today; I am excited and have it in control.",
            ignore_quiet_hours=True,
            subjective_rating=8,
        )
        self.assertEqual(rep_day20["step_2_detection"]["status"], "AUTONOMIC_ANOMALY")
        self.assertEqual(rep_day20["step_3_dialogue"]["appraisal_category"], "EUSTRESS")
        self.assertEqual(rep_day20["step_4_ledger_entry"]["status"], "RECORDED")

        # Run day 21: Morning cron runs -> Verifies day 20 recovery -> Reflects to memory
        rep_day21 = orchestrator.run_pipeline(
            target_date=next_str,
            health_db=self.health_db,
            ledger_db=self.ledger_db,
            memory_path=self.memory_file,
            state_file=state_file,
            ignore_quiet_hours=True,
        )
        self.assertEqual(rep_day21["step_1_verification"]["verified_count"], 1)
        ver_details = rep_day21["step_1_verification"]["details"][0]
        self.assertEqual(ver_details["status"], "REBOUND_CONFIRMED")

        # Memory was updated
        mem_text = self.memory_file.read_text(encoding="utf-8")
        self.assertIn("Task Boundary Defense", mem_text)

        # Weekly recap
        recap = ledger.generate_weekly_recap(self.ledger_db)
        self.assertIn("Weekly Recap:", recap)

    def test_runtime_installer(self):
        import install_runtime
        inst_dir = Path(self.temp_dir) / "test_hermes_runtime"
        report = install_runtime.install_runtime(inst_dir)
        self.assertTrue((inst_dir / "skills").is_dir())
        self.assertTrue((inst_dir / "SOUL.md").is_file())
        self.assertTrue((inst_dir / "memories" / "MEMORY.md").is_file())
        self.assertTrue((inst_dir / "data").is_dir())
        self.assertTrue((inst_dir / "state").is_dir())

        # Second install preserves personalized files
        user_file = inst_dir / "memories" / "USER.md"
        user_file.write_text("CUSTOM_USER_DATA", encoding="utf-8")
        report2 = install_runtime.install_runtime(inst_dir)
        self.assertIn("USER.md", report2["preserved_profiles"])
        self.assertEqual(user_file.read_text(encoding="utf-8"), "CUSTOM_USER_DATA")


if __name__ == "__main__":
    unittest.main()
