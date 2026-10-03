"""Unit tests for Gate 2: Cognitive Appraisal & Action Triage."""

import json
from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "skills" / "stress-dialogue" / "scripts"))

import dialogue_engine  # noqa: E402


class TestGate2Dialogue(unittest.TestCase):
    def setUp(self):
        self.anomaly_payload = {
            "date": "2026-10-03",
            "triggered_metric": "hrv_score",
            "deviation_sigma": -1.9,
        }

    def test_eustress_classification_and_action(self):
        summary = dialogue_engine.run_dialogue(
            anomaly_payload=self.anomaly_payload,
            mock_responses=["We are launching today; I am excited and have it in control."],
            subjective_rating=6,
        )
        self.assertEqual(summary["status"], "COMPLETED")
        self.assertEqual(summary["appraisal_category"], "EUSTRESS")
        self.assertEqual(summary["cause_id"], "CHALLENGE_LOAD")
        self.assertEqual(summary["intervention_id"], "PRIORITY_LOCK")
        self.assertEqual(summary["subjective_rating"], 6)
        self.assertLessEqual(summary["turn_count"], 3)
        self.assertIn("priority milestone", summary["intervention_type"].lower())

    def test_distress_threat_precedence_over_eustress(self):
        # Even with "deadline" or "project", threat/layoff/conflict language MUST map to DISTRESS
        summary = dialogue_engine.run_dialogue(
            anomaly_payload=self.anomaly_payload,
            mock_responses=["My boss is threatening layoffs before the project deadline."],
        )
        self.assertEqual(summary["status"], "COMPLETED")
        self.assertEqual(summary["appraisal_category"], "DISTRESS")
        self.assertEqual(summary["cause_id"], "ACUTE_THREAT")
        self.assertEqual(summary["intervention_id"], "PHYSIOLOGICAL_SIGH")

    def test_low_control_with_deadline_maps_to_distress(self):
        # Explicit reproduction test: 'My deadline is impossible and I have no control'
        summary = dialogue_engine.run_dialogue(
            anomaly_payload=self.anomaly_payload,
            mock_responses=["My deadline is impossible and I have no control."],
        )
        self.assertEqual(summary["status"], "COMPLETED")
        self.assertEqual(summary["appraisal_category"], "DISTRESS")
        self.assertEqual(summary["cause_id"], "ACUTE_THREAT")
        self.assertEqual(summary["intervention_id"], "PHYSIOLOGICAL_SIGH")

    def test_max_turns_two_budget_respected(self):
        # Explicit reproduction test: max_turns=2 with ambiguous inputs must not exceed 2 turns!
        summary = dialogue_engine.run_dialogue(
            anomaly_payload=self.anomaly_payload,
            mock_responses=["idk", "idk"],
            max_turns=2,
        )
        self.assertEqual(summary["status"], "COMPLETED")
        self.assertLessEqual(summary["turn_count"], 2)

    def test_action_acceptance_detection(self):
        summary = dialogue_engine.run_dialogue(
            anomaly_payload=self.anomaly_payload,
            mock_responses=["I feel overwhelmed by this deadline.", "Will do."],
        )
        self.assertEqual(summary["action_accepted"], True)

    def test_anxiety_maps_to_distress(self):
        summary = dialogue_engine.run_dialogue(
            anomaly_payload=self.anomaly_payload,
            mock_responses=["I am super anxious about my presentation today."],
        )
        self.assertEqual(summary["status"], "COMPLETED")
        self.assertEqual(summary["appraisal_category"], "DISTRESS")

    def test_recovery_drain_classification(self):
        summary = dialogue_engine.run_dialogue(
            anomaly_payload=self.anomaly_payload,
            mock_responses=["I haven't slept properly for three nights and feel completely exhausted."],
        )
        self.assertEqual(summary["status"], "COMPLETED")
        self.assertEqual(summary["appraisal_category"], "RECOVERY_DRAIN")
        self.assertEqual(summary["cause_id"], "RECOVERY_DEFICIT")
        self.assertEqual(summary["intervention_id"], "SCREEN_CURFEW")
        self.assertLessEqual(summary["turn_count"], 3)

    def test_uncertain_followup_and_turn3_resolution(self):
        # User answers coach's offered option "workload"
        summary = dialogue_engine.run_dialogue(
            anomaly_payload=self.anomaly_payload,
            mock_responses=["Not sure", "Heavy workload, but manageable; I have a plan."],
        )
        self.assertEqual(summary["status"], "COMPLETED")
        self.assertEqual(summary["turn_count"], 3)
        self.assertEqual(summary["appraisal_category"], "EUSTRESS")
        self.assertEqual(summary["intervention_id"], "PRIORITY_LOCK")

    def test_uncertain_category_retained_if_ambiguous(self):
        # User remains ambiguous after clarifying question -> UNCERTAIN is preserved
        summary = dialogue_engine.run_dialogue(
            anomaly_payload=self.anomaly_payload,
            mock_responses=["Idk", "Still not sure, just stuff"],
        )
        self.assertEqual(summary["status"], "COMPLETED")
        self.assertEqual(summary["appraisal_category"], "UNCERTAIN")
        self.assertEqual(summary["intervention_id"], "GROUNDING_PAUSE")

    def test_rumination_circuit_breaker(self):
        summary = dialogue_engine.run_dialogue(
            anomaly_payload=self.anomaly_payload,
            mock_responses=["Why does this always happen to me? I can't stop thinking, everything is ruined and hopeless!"],
        )
        self.assertEqual(summary["status"], "CIRCUIT_BREAKER_TRIGGERED")
        self.assertEqual(summary["turn_count"], 2)
        last_coach_msg = summary["transcript"][-1]["message"]
        self.assertIn("reinforces rumination rather than recovery", last_coach_msg)
        self.assertIn("Prescribed micro-action:", last_coach_msg)


if __name__ == "__main__":
    unittest.main()
