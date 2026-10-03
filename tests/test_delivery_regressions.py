"""Failure, restart, and isolation tests for the reviewed delivery gaps."""
from contextlib import closing
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
for skill in ("detect-baseline", "stress-dialogue", "stress-ledger", "samsung-health-import"):
    sys.path.insert(0, str(ROOT / "skills" / skill / "scripts"))
import baseline_math
import dialogue_engine as dialogue
import import_samsung
import install_runtime
import ledger
import messaging_gateway as gateway
import orchestrator
import simulate_trigger
from runtime_config import runtime_home


class FakeTransport:
    chat_id = "101"
    user_id = "202"

    def __init__(self):
        self.sent = []
        self.incoming = []
        self.fail = False

    def send(self, text):
        self.sent.append(text)
        if self.fail:
            raise RuntimeError("simulated network timeout")
        return len(self.sent)

    def updates(self, offset):
        return [u for u in self.incoming if u["update_id"] >= offset]

    def reply(self, event_id, reply_to, text, user=None):
        return {"update_id": event_id, "message": {
            "chat": {"id": int(self.chat_id), "type": "private"},
            "from": {"id": int(user or self.user_id)}, "text": text,
            "reply_to_message": {"message_id": reply_to}}}


class DeliveryRegressions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.transport = FakeTransport()
        self.dispatcher = gateway.ChannelDispatcher("telegram", self.base / "spool", transport=self.transport)
        self.db = self.base / "ledger.db"
        self.anomaly = {"date": "2026-10-01", "triggered_metric": "hrv_score",
                        "deviation_sigma": -2, "metric_sources": {"hrv_score": "samsung"},
                        "baseline_mean": 60, "baseline_std": 2,
                        "confounder_status": "WORKOUT_DATA_MISSING_UNVERIFIED",
                        "uncertainty_flags": ["WORKOUT_DATA_MISSING_UNVERIFIED"], "is_simulated": False}

    def start(self):
        session = dialogue.DialogueSession(self.anomaly)
        return self.dispatcher.dispatch(session.start(), event_id="coach_1",
                                        context={"anomaly": self.anomaly}).session_id

    def test_telegram_http_contract_and_redacted_errors(self):
        calls = []
        def opener(req, timeout):
            calls.append((req, timeout))
            return io.BytesIO(json.dumps({"ok": True, "result": {"message_id": 7}}).encode())
        transport = gateway.TelegramTransport("fixture-token", "101", "202", opener=opener)
        self.assertEqual(transport.send("hello"), 7)
        req, timeout = calls[0]
        self.assertTrue(req.full_url.endswith("/sendMessage"))
        payload = json.loads(req.data)
        self.assertEqual(payload["chat_id"], "101")
        self.assertTrue(payload["reply_markup"]["force_reply"])
        with patch.object(transport, "_opener", side_effect=RuntimeError("fixture-token")):
            with self.assertRaises(RuntimeError) as error:
                transport.updates(8)
        self.assertNotIn("fixture-token", str(error.exception))

    def test_duplicate_outbound_never_resends_after_restart(self):
        session_id = self.start()
        restarted = gateway.ChannelDispatcher("telegram", self.base / "spool", transport=self.transport)
        restarted.dispatch("same event", session_id, event_id="coach_1")
        self.assertEqual(len(self.transport.sent), 1)

    def test_uncertain_delivery_never_resends(self):
        self.transport.fail = True
        with self.assertRaises(RuntimeError):
            self.dispatcher.dispatch("test", "fixed_session", event_id="coach_1")
        self.transport.fail = False
        event = self.dispatcher.dispatch("test", "fixed_session", event_id="coach_1")
        self.assertEqual(event.delivery_status, "DELIVERY_UNCERTAIN")
        self.assertEqual(len(self.transport.sent), 1)

    def test_crash_during_send_stays_uncertain(self):
        session_id = self.start()
        data = self.dispatcher.load(session_id)
        data["status"] = "SENDING"
        data["events"][0]["delivery_status"] = "SENDING"
        self.dispatcher.save(data)
        self.assertEqual(self.dispatcher.check_session_status(session_id), "DELIVERY_UNCERTAIN")
        self.dispatcher.dispatch("test", session_id, event_id="coach_1")
        self.assertEqual(len(self.transport.sent), 1)

    def test_sender_and_reply_to_binding(self):
        session_id = self.start()
        self.assertIsNone(self.dispatcher.correlate_update(self.transport.reply(1, 1, "hello", user="999")))
        self.assertIsNone(self.dispatcher.correlate_update(self.transport.reply(1, 9, "hello")))
        self.assertEqual(self.dispatcher.correlate_update(self.transport.reply(1, 1, "hello"))[0], session_id)

    def test_missing_reply_expires_without_outbound(self):
        session_id = self.start()
        data = self.dispatcher.load(session_id)
        data["awaiting_since"] = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        self.dispatcher.save(data)
        orchestrator.poll_once(self.dispatcher, self.db)
        self.assertEqual(self.dispatcher.check_session_status(session_id), "EXPIRED_NO_REPLY")
        with self.assertRaises(TimeoutError):
            self.dispatcher.record_reply(session_id, "late", "late_id")
        self.assertEqual(len(self.transport.sent), 1)
        self.assertFalse(self.db.exists())

    def test_live_poll_duplicate_reply_and_confirmation_journal(self):
        session_id = self.start()
        self.transport.incoming = [self.transport.reply(1, 1, "I feel overwhelmed by the deadline.")]
        self.assertEqual(orchestrator.poll_once(self.dispatcher, self.db), 1)
        self.assertEqual(self.dispatcher.check_session_status(session_id), "AWAITING_CONFIRMATION")
        self.assertEqual(len(self.transport.sent), 2)
        orchestrator.poll_once(self.dispatcher, self.db)
        self.assertEqual(len(self.transport.sent), 2)
        self.transport.incoming.append(self.transport.reply(2, 2, "Yes"))
        orchestrator.poll_once(self.dispatcher, self.db)
        self.assertEqual(self.dispatcher.check_session_status(session_id), "COMPLETED")
        with closing(sqlite3.connect(self.db)) as conn, conn:
            row = conn.execute("SELECT action_accepted, action_completed, metric_source, uncertainty_flags FROM stress_ledger").fetchone()
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM stress_ledger").fetchone()[0], 1)
        self.assertEqual(row[:3], (1, None, "samsung"))
        self.assertIn("WORKOUT_DATA_MISSING_UNVERIFIED", row[3])
        self.assertIn("cause remains uncertain", self.transport.sent[0])
        self.assertEqual(len(self.transport.sent), 2)

    def test_reply_journal_recovers_before_cursor_ack(self):
        session_id = self.start()
        self.dispatcher.record_reply(session_id, "I am anxious about the deadline", "telegram_1")
        orchestrator.poll_once(self.dispatcher, self.db)
        self.assertEqual(len(self.transport.sent), 2)
        with closing(sqlite3.connect(self.db)) as conn, conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM stress_ledger").fetchone()[0], 1)
        # Simulate crash after side effects, before the worker saved its summary.
        data = self.dispatcher.load(session_id)
        data["status"] = "REPLY_RECEIVED"
        self.dispatcher.save(data)
        orchestrator.poll_once(self.dispatcher, self.db)
        self.assertEqual(len(self.transport.sent), 2)
        self.assertEqual(ledger.get_ledger_report(self.db)["total_entries"], 1)

    def test_ambiguous_context_never_implies_action_acceptance(self):
        result = dialogue.run_dialogue(self.anomaly, ["Not sure about my deadline", "Not sure"])
        self.assertEqual(result["appraisal_category"], "UNCERTAIN")
        self.assertIsNone(result["action_accepted"])
        self.assertEqual(result["turn_count"], 3)
        for text in ("I am not sure", "yesterday", "not done", "I am okay with the workload"):
            self.assertIsNone(dialogue.detect_action_acceptance(text))
        self.assertFalse(dialogue.detect_action_acceptance("No, I won't do it"))

    def test_acceptance_and_completion_require_post_proposal_reply(self):
        first = dialogue.run_dialogue(self.anomaly, ["Sounds good"])
        self.assertIsNone(first["action_accepted"])
        accepted = dialogue.run_dialogue(self.anomaly, ["I feel overwhelmed", "Yes"])
        self.assertTrue(accepted["action_accepted"])
        self.assertIsNone(accepted["action_completed"])
        completed = dialogue.run_dialogue(self.anomaly, ["I feel overwhelmed", "Done"])
        self.assertTrue(completed["action_completed"])

    def test_no_reply_or_eof_does_not_invent_context(self):
        summary = dialogue.run_dialogue(self.anomaly)
        self.assertEqual(summary["status"], "ACTIVE")
        self.assertEqual(summary["turn_count"], 1)
        self.assertIsNone(summary["intervention_id"])
        with patch("builtins.input", side_effect=EOFError), patch("builtins.print"):
            summary = dialogue.run_dialogue(self.anomaly, interactive=True)
        self.assertIsNone(summary["intervention_id"])
        result = simulate_trigger.run_session(self.anomaly, state_file=self.base / "dispatch.json", ignore_quiet_hours=True)
        self.assertEqual(result["status"], "AWAITING_REPLY")
        self.assertFalse(simulate_trigger.check_daily_dispatch(self.base / "dispatch.json", self.anomaly["date"]))

    def test_runtime_paths_installation_and_personal_content(self):
        home = self.base / "hermes"
        with patch.dict(os.environ, {"HERMES_HOME": str(home)}):
            self.assertEqual(runtime_home(), install_runtime.get_default_runtime_dir())
            paths = orchestrator.get_runtime_paths()
            self.assertEqual(paths["memory_path"], home / "memories" / "MEMORY.md")
            install_runtime.install_runtime(home)
            soul = home / "SOUL.md"
            soul.write_text("personal persona", encoding="utf-8")
            memory = paths["memory_path"]
            memory.write_text("personal memory", encoding="utf-8")
            skill = home / "skills" / "stress-dialogue" / "SKILL.md"
            skill.write_text("custom skill", encoding="utf-8")
            report = install_runtime.install_runtime(home)
        self.assertEqual(soul.read_text(), "personal persona")
        self.assertEqual(memory.read_text(), "personal memory")
        backups = [Path(p) for p in report["skill_backups"] if p.endswith("stress-dialogue")]
        self.assertEqual((backups[0] / "SKILL.md").read_text(), "custom skill")

    def test_mixed_provider_history_cannot_meet_minimum(self):
        history = [{"date": f"2026-09-{i + 1:02d}", "hrv_score": 60 + i % 3,
                    "metric_sources": {"hrv_score": "samsung" if i < 8 else "garmin"}}
                   for i in range(20)]
        target = {"date": "2026-09-21", "hrv_score": 40, "metric_sources": {"hrv_score": "garmin"}}
        result = baseline_math.evaluate_day_metrics(target, None, history)
        self.assertFalse(result["dispatch_trigger"])
        self.assertEqual(result["status"], "INSUFFICIENT_HISTORY")

    def test_live_pipeline_waits_for_reply_and_reserves_daily_limit(self):
        health = self.base / "health.db"
        conn = import_samsung.init_db(health)
        with conn:
            for day in range(1, 21):
                conn.execute("INSERT INTO daily_metrics(date,hrv_score,workout_strain_score,source) VALUES (?,?,?,?)",
                             (f"2026-09-{day:02d}", 60 + day % 3, 3, "samsung"))
            conn.execute("INSERT INTO daily_metrics(date,hrv_score,workout_strain_score,source) VALUES (?,?,?,?)",
                         ("2026-09-21", 40, 3, "samsung"))
        conn.close()
        kwargs = dict(target_date="2026-09-21", health_db=health, ledger_db=self.db,
                      state_file=self.base / "dispatch.json", memory_path=self.base / "MEMORY.md",
                      ignore_quiet_hours=True, dispatcher=self.dispatcher)
        report = orchestrator.run_pipeline(**kwargs)
        summary = report["step_3_dialogue"]
        self.assertEqual(summary["status"], "ACTIVE")
        self.assertFalse(summary["is_simulated"])
        self.assertIsNone(summary["intervention_id"])
        self.assertIsNone(report["step_4_ledger_entry"])
        repeat = orchestrator.run_pipeline(**kwargs)
        self.assertEqual(repeat["step_2_detection"]["dispatch_suppressed"], "Already dispatched today")
        self.transport.incoming = [self.transport.reply(1, 1, "I feel anxious about tomorrow.")]
        orchestrator.poll_once(self.dispatcher, self.db)
        with closing(sqlite3.connect(self.db)) as conn:
            row = conn.execute("SELECT baseline_mean,baseline_std,metric_source,is_simulated,action_accepted FROM stress_ledger").fetchone()
        self.assertGreater(row[0], 60)
        self.assertGreater(row[1], 0)
        self.assertEqual(row[2:], ("samsung", 0, None))

    def test_short_workout_history_remains_uncertain(self):
        status, reason = baseline_math.evaluate_workout_confounder(3, [2, 3, 4])
        self.assertEqual(status, "WORKOUT_HISTORY_UNVERIFIED")
        self.assertIn("uncertain", reason)

    def test_legacy_schema_migrates_without_losing_records(self):
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("""CREATE TABLE stress_ledger (
                id INTEGER PRIMARY KEY, date TEXT, trigger_metric TEXT, deviation_sigma REAL,
                attributed_cause TEXT, cause_id TEXT, intervention_type TEXT, intervention_id TEXT,
                subjective_rating INTEGER, next_day_date TEXT, next_day_metric_val REAL,
                next_day_sigma REAL, next_day_rebound_delta REAL, rebound_status TEXT,
                created_at TEXT, verified_at TEXT)""")
            conn.execute("INSERT INTO stress_ledger(id,date,trigger_metric,intervention_type) VALUES (1,'2026-10-01','hrv_score','pause')")
        conn = ledger.init_ledger_db(self.db)
        try:
            row = conn.execute("SELECT id,intervention_type,action_completed,is_simulated FROM stress_ledger").fetchone()
        finally:
            conn.close()
        self.assertEqual(row, (1, "pause", None, None))

    def test_duplicate_ingest_cannot_erase_confirmed_action(self):
        kwargs = dict(db_path=self.db, trigger_metric="hrv_score", attributed_cause="possible workload",
                      intervention_type="pause", session_id="same-session")
        first = ledger.add_ledger_entry(**kwargs, action_accepted=True, action_completed=True)
        second = ledger.add_ledger_entry(**kwargs)
        self.assertEqual(first, second)
        with closing(sqlite3.connect(self.db)) as conn:
            row = conn.execute("SELECT action_accepted,action_completed FROM stress_ledger").fetchone()
        self.assertEqual(row, (1, 1))

    def test_wrong_provider_cannot_verify_missing_followup(self):
        health = self.base / "health.db"
        conn = import_samsung.init_db(health)
        with conn:
            conn.execute("INSERT INTO daily_metrics(date,hrv_score,source) VALUES ('2026-08-02',60,'samsung')")
        conn.close()
        ledger.add_ledger_entry(self.db, "hrv_score", "possible workload", "pause",
                               date_str="2026-08-01", metric_source="garmin", baseline_mean=60, baseline_std=2)
        self.assertEqual(ledger.verify_next_day_recovery(self.db, health), [])
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute("SELECT rebound_status FROM stress_ledger").fetchone()[0], "EXPIRED_NO_DATA")

    def test_followup_matches_frozen_source_even_with_other_provider_first(self):
        samsung = self.base / "health.db"
        garmin = self.base / "garmin.db"
        for db, source, value in ((samsung, "samsung", 60), (garmin, "garmin", 20)):
            conn = import_samsung.init_db(db)
            with conn:
                conn.execute("INSERT INTO daily_metrics(date,hrv_score,source) VALUES (?,?,?)",
                             ("2026-10-02", value, source))
            conn.close()
        ledger.add_ledger_entry(self.db, "hrv_score", "possible workload", "pause",
                               date_str="2026-10-01", deviation_sigma=-2, session_id="source-test",
                               metric_source="garmin", baseline_mean=60, baseline_std=2)
        result = ledger.verify_next_day_recovery(self.db, samsung, garmin)
        self.assertEqual(result[0]["next_sigma"], -20)
        self.assertEqual(result[0]["status"], "NO_REBOUND")

    def test_unknown_completion_and_mock_records_do_not_enter_habit_summary(self):
        for i, complete, simulated, source in ((0, None, False, "samsung"), (1, True, True, "samsung"),
                                               (2, True, False, "samsung"), (3, True, False, "garmin")):
            row = ledger.add_ledger_entry(self.db, "hrv_score", "possible challenge", "pause",
                                         session_id=f"record_{i}", action_completed=complete,
                                         is_simulated=simulated, metric_source=source,
                                         confounder_status="NO_CONFOUNDER_DETECTED", appraisal_category="EUSTRESS")
            with closing(sqlite3.connect(self.db)) as conn, conn:
                conn.execute("UPDATE stress_ledger SET rebound_status='REBOUND_CONFIRMED', next_day_rebound_delta=2 WHERE id=?", (row,))
        report = ledger.get_ledger_report(self.db)
        self.assertEqual(report["excluded_from_action_summary"], 2)
        self.assertEqual(len(report["interventions"]), 2)
        self.assertTrue(all(not s["has_minimum_sample"] for s in report["interventions"].values()))


if __name__ == "__main__":
    unittest.main()
