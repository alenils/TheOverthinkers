"""Unit tests for Matrix OS status generator contract."""

from pathlib import Path
import tempfile
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

import sys
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
import generate_matrix_status  # noqa: E402
import ledger  # noqa: E402


class TestMatrixStatusGenerator(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        self.ledger_db = self.temp_path / "data" / "ledger.db"

    def test_generate_status_schema(self):
        status = generate_matrix_status.generate_status()

        # Contract assertions
        self.assertIn("timestamp", status)
        self.assertIn("agent", status)
        self.assertIn("model", status)
        self.assertIn("tts", status)
        self.assertIn("gateway", status)
        self.assertIn("cron_jobs", status)
        self.assertIn("skills", status)
        self.assertIn("ledger", status)
        self.assertIn("profiles", status)
        self.assertIn("quick_commands", status)

        # Privacy assertion: memory_preview must not be exposed
        self.assertNotIn("memory_preview", status["profiles"])
        self.assertIn("has_soul", status["profiles"])
        self.assertIn("has_user", status["profiles"])
        self.assertIn("has_memory", status["profiles"])

        # Model & TTS assertions
        self.assertEqual(status["agent"]["persona"], "The Self-Distanced Observer")
        self.assertGreaterEqual(len(status["skills"]), 6)
        self.assertGreaterEqual(len(status["quick_commands"]), 4)

    def test_ledger_data_contract_alignment(self):
        # Create a test ledger with 2 entries (1 confirmed rebound)
        ledger.init_ledger_db(self.ledger_db)
        e1 = ledger.add_ledger_entry(
            self.ledger_db, "hrv_score", "Friction 1", "Action 1",
            date_str="2026-10-01", deviation_sigma=-1.8,
        )
        ledger.add_ledger_entry(
            self.ledger_db, "hrv_score", "Friction 2", "Action 2",
            date_str="2026-10-02", deviation_sigma=-2.0,
        )
        conn = ledger.init_ledger_db(self.ledger_db)
        with conn:
            conn.execute(
                "UPDATE stress_ledger SET rebound_status = 'REBOUND_CONFIRMED' WHERE id = ?",
                (e1,),
            )
        conn.close()

        # Patch HEALTH_DIR to temp_path
        old_health = generate_matrix_status.HEALTH_DIR
        try:
            generate_matrix_status.HEALTH_DIR = self.temp_path
            ledger_data = generate_matrix_status.get_ledger_data()

            self.assertEqual(ledger_data["total_entries"], 2)
            self.assertEqual(ledger_data["confirmed_rebounds"], 1)
            # Rebound rate in ledger_report: 1 confirmed / 1 verified = 100%
            self.assertEqual(ledger_data["recovery_rate_pct"], 100.0)
            self.assertEqual(len(ledger_data["entries"]), 2)
        finally:
            generate_matrix_status.HEALTH_DIR = old_health


if __name__ == "__main__":
    unittest.main()
