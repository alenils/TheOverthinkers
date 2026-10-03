"""Unit tests for Gate 0: Steel Thread & Profile Bootstrap."""

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import simulate_trigger  # noqa: E402


class TestGate0Bootstrap(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_profile_files_exist(self):
        soul = PROJECT_ROOT / "Profile" / "SOUL.md"
        user = PROJECT_ROOT / "Profile" / "USER.md"
        memory = PROJECT_ROOT / "Profile" / "MEMORY.md"

        self.assertTrue(soul.is_file(), "Profile/SOUL.md must exist")
        self.assertTrue(user.is_file(), "Profile/USER.md must exist")
        self.assertTrue(memory.is_file(), "Profile/MEMORY.md must exist")

    def test_soul_content_invariants(self):
        soul_text = (PROJECT_ROOT / "Profile" / "SOUL.md").read_text(encoding="utf-8")
        self.assertIn("The Self-Distanced Observer", soul_text)
        self.assertIn("The Concise Operator", soul_text)
        self.assertIn("Silence by Default", soul_text)
        self.assertIn("Anti-Rumination Circuit Breaker", soul_text)

    def test_user_scaffold_invariants(self):
        user_text = (PROJECT_ROOT / "Profile" / "USER.md").read_text(encoding="utf-8")
        self.assertIn("health.db", user_text)
        self.assertIn("garmin.db", user_text)
        self.assertIn("Quiet Hours", user_text)

    def test_profile_loading_failure_loud(self):
        empty_dir = Path(self.temp_dir) / "empty_profile"
        empty_dir.mkdir()
        with self.assertRaises(FileNotFoundError):
            simulate_trigger.load_profile(empty_dir)

    def test_simulate_trigger_execution(self):
        state_file = Path(self.temp_dir) / "state.json"
        res = simulate_trigger.run_session(
            anomaly_data={"date": "2026-10-01", "metric": "hrv_deviation", "deviation_sigma": -1.8},
            mock_reply="I have a major deadline today and three back-to-back reviews.",
            state_file=state_file,
            ignore_quiet_hours=True,
        )
        self.assertEqual(res["status"], "TERMINATED")
        self.assertEqual(res["turn_count"], 2)
        self.assertEqual(len(res["transcript"]), 3)
        self.assertIn("SOUL.md", res["profile_loaded"])
        self.assertIn("[Simulated Alert]", res["transcript"][0]["message"])
        self.assertIn("event_id", res["transcript"][0])

        # Second dispatch on the same date should be suppressed (once-per-day rule)
        res_dup = simulate_trigger.run_session(
            anomaly_data={"date": "2026-10-01", "metric": "hrv_deviation", "deviation_sigma": -1.8},
            mock_reply="Another ping on same day",
            state_file=state_file,
            ignore_quiet_hours=True,
        )
        self.assertEqual(res_dup["status"], "SUPPRESSED_ALREADY_DISPATCHED")

    def test_rumination_circuit_breaker(self):
        state_file = Path(self.temp_dir) / "state_rum.json"
        res = simulate_trigger.run_session(
            anomaly_data={"date": "2026-10-02", "metric": "hrv_deviation", "deviation_sigma": -1.8},
            mock_reply="I can't stop thinking why does this always happen everything is ruined and hopeless!",
            state_file=state_file,
            ignore_quiet_hours=True,
        )
        self.assertEqual(res["status"], "TERMINATED")
        turn2_coach = res["transcript"][2]["message"]
        self.assertIn("reinforces rumination rather than recovery", turn2_coach)
        self.assertIn("Take 3 physiological sighs", turn2_coach)


if __name__ == "__main__":
    unittest.main()
