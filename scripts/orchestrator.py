#!/usr/bin/env python3
"""Daily detection, durable bounded dialogue, and matched follow-up observations."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for folder in ("detect-baseline", "stress-dialogue", "stress-ledger"):
    sys.path.insert(0, str(PROJECT_ROOT / "skills" / folder / "scripts"))
import baseline_math
import dialogue_engine
import ledger
import messaging_gateway as gateway
import simulate_trigger
from runtime_config import runtime_paths


def local_now():
    name = os.environ.get("STRESS_TIMEZONE", "UTC")
    return datetime.now(timezone.utc if name == "UTC" else ZoneInfo(name))


def get_runtime_paths():
    return runtime_paths()


def store_summary(db_path, summary):
    if not summary.get("intervention_id"):
        return None
    return ledger.add_ledger_entry(
        db_path=db_path, trigger_metric=summary["trigger_metric"],
        attributed_cause=summary["attributed_cause"], intervention_type=summary["intervention_type"],
        date_str=summary["date"], deviation_sigma=summary["deviation_sigma"],
        **{key: summary.get(key) for key in (
            "cause_id", "intervention_id", "subjective_rating", "session_id", "metric_source",
            "baseline_mean", "baseline_std", "uncertainty_flags", "confounder_status",
            "action_accepted", "action_completed", "is_simulated", "appraisal_category")})


def resume_session(dispatcher, session_id, ledger_db):
    """Replay journaled replies; stable coach IDs protect crash recovery from resends."""
    data = dispatcher.load(session_id)
    session = dialogue_engine.DialogueSession(data["context"]["anomaly"])
    session.start()
    simulated = data["context"]["anomaly"].get("is_simulated", False)
    for event in data["events"]:
        if event["direction"] != "INBOUND":
            continue
        if session.status == "ACTIVE":
            reply = session.process_user_turn(event["text"], data["context"].get("subjective_rating"))
            if reply:
                outbound = dispatcher.dispatch(reply, session_id, simulated,
                                               event_id=f"coach_{session.turn_count}")
                if outbound.delivery_status not in ("DELIVERED", "MOCK_RECORDED"):
                    return {"status": "DELIVERY_UNCERTAIN", "session_id": session_id}
        else:
            session.confirm_action(event["text"])
    summary = session.get_summary()
    summary.update(session_id=session_id, is_simulated=simulated)
    entry_id = store_summary(ledger_db, summary)
    current = dispatcher.load(session_id)
    if session.confirmation_received:
        current["status"] = "COMPLETED"
    elif session.status != "ACTIVE":
        current["status"] = "AWAITING_CONFIRMATION"
    else:
        current["status"] = "AWAITING_REPLY"
    current["summary"] = summary
    current["ledger_entry_id"] = entry_id
    dispatcher.save(current)
    return summary


def poll_once(dispatcher, ledger_db):
    """Expire silently, recover journaled replies, then acknowledge processed updates."""
    with gateway.ConcurrencyLock(dispatcher.spool_dir / ".worker.lock"):
        for path in dispatcher.spool_dir.glob("session_*.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            status = dispatcher.check_session_status(data["session_id"])
            if status == "REPLY_RECEIVED":
                resume_session(dispatcher, data["session_id"], ledger_db)
        cursor_path = dispatcher.spool_dir / "telegram_cursor.json"
        cursor = json.loads(cursor_path.read_text()) if cursor_path.exists() else {"offset": 0}
        processed = 0
        for update in dispatcher.transport.updates(cursor["offset"]):
            if update["update_id"] < cursor["offset"]:
                continue
            matched = dispatcher.correlate_update(update)
            if matched:
                session_id, text, event_id = matched
                dispatcher.record_reply(session_id, text, event_id)
                resume_session(dispatcher, session_id, ledger_db)
                processed += 1
            # Cursor advances only after the reply and downstream work are durable.
            cursor["offset"] = update["update_id"] + 1
            gateway.save_json(cursor_path, cursor)
        return processed


def run_pipeline(target_date, health_db, garmin_db=None, ledger_db=None, memory_path=None,
                 state_file=None, mock_reply=None, interactive=False, ignore_quiet_hours=False,
                 subjective_rating=None, channel=None, dispatcher=None, mock_confirmation=None):
    paths = get_runtime_paths()
    ledger_db = Path(ledger_db or paths["ledger_db"])
    memory_path = Path(memory_path or paths["memory_path"])
    state_file = Path(state_file or paths["state_file"])
    report = {"date": target_date, "step_1_verification": None, "step_2_detection": None,
              "step_3_dialogue": None, "step_4_ledger_entry": None}
    verified = ledger.verify_next_day_recovery(ledger_db, health_db, garmin_db)
    report["step_1_verification"] = {"verified_count": len(verified), "details": verified}
    if verified and memory_path.is_file():
        ledger.reflect_to_memory(ledger_db, memory_path)
    sources = [health_db] + ([garmin_db] if garmin_db and garmin_db.is_file() else [])
    target, prior, history = baseline_math.load_unified_series(sources, target_date)
    if not target:
        report["step_2_detection"] = {"status": "NO_DATA"}
        return report
    anomaly = baseline_math.evaluate_day_metrics(target, prior, history)
    report["step_2_detection"] = anomaly
    if not anomaly.get("dispatch_trigger"):
        return report
    now = local_now()
    if not ignore_quiet_hours and not baseline_math.check_quiet_hours(now, os.environ.get("STRESS_ALLOWED_HOURS", "08:00-21:00")):
        anomaly["dispatch_suppressed"] = "Quiet hours"
        return report
    channel = channel or ("mock" if mock_reply is not None or interactive else None)
    if dispatcher is None and channel is None:
        anomaly["dispatch_suppressed"] = "No channel selected; use --channel telegram or explicit mock/interactive mode"
        return report
    dispatcher = dispatcher or gateway.ChannelDispatcher(channel, state_file.parent / "messaging")
    anomaly["is_simulated"] = dispatcher.channel == "mock"
    date_key = now.strftime("%Y-%m-%d")
    # The anomaly date identifies the measurement; the local date limits outreach.
    with gateway.ConcurrencyLock(state_file.with_suffix(".lock")):
        if not simulate_trigger.check_daily_dispatch(state_file, date_key):
            anomaly["dispatch_suppressed"] = "Already dispatched today"
            return report
        simulate_trigger.record_dispatch(state_file, date_key)  # Reserve before HTTP.
        session = dialogue_engine.DialogueSession(anomaly)
        outbound = dispatcher.dispatch(session.start(), is_simulated=anomaly["is_simulated"],
                                       event_id="coach_1", context={"anomaly": anomaly, "subjective_rating": subjective_rating})
    session_id = outbound.session_id
    summary = session.get_summary()
    summary.update(session_id=session_id, is_simulated=anomaly["is_simulated"])
    if interactive:
        print(outbound.text)
        try:
            mock_reply = input("[User reply]: ").strip()
        except (EOFError, KeyboardInterrupt):
            mock_reply = None
    if mock_reply and dispatcher.channel == "mock":
        dispatcher.record_reply(session_id, mock_reply, event_id="mock_context")
        summary = resume_session(dispatcher, session_id, ledger_db)
        while interactive and summary["status"] == "ACTIVE":
            print(summary["transcript"][-1]["message"])
            try:
                text = input("[User reply]: ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not text:
                break
            dispatcher.record_reply(session_id, text)
            summary = resume_session(dispatcher, session_id, ledger_db)
        if summary.get("intervention_id"):
            if interactive:
                print(summary["transcript"][-1]["message"])
                try:
                    mock_confirmation = input("[Action confirmation, optional]: ").strip()
                except (EOFError, KeyboardInterrupt):
                    mock_confirmation = None
            if mock_confirmation:
                dispatcher.record_reply(session_id, mock_confirmation, event_id="mock_confirmation")
                summary = resume_session(dispatcher, session_id, ledger_db)
    report["step_3_dialogue"] = summary
    data = dispatcher.load(session_id)
    if data.get("ledger_entry_id"):
        report["step_4_ledger_entry"] = {"entry_id": data["ledger_entry_id"], "status": "RECORDED"}
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("date", "health-db", "garmin-db", "ledger-db", "memory-path", "state-file", "mock-reply", "mock-confirmation"):
        parser.add_argument(f"--{name}")
    parser.add_argument("--channel", choices=["telegram", "mock"])
    for name in ("interactive", "ignore-quiet-hours", "recap", "poll", "watch"):
        parser.add_argument(f"--{name}", action="store_true")
    args = parser.parse_args()
    paths = get_runtime_paths()
    for name in paths:
        if getattr(args, name, None):
            paths[name] = Path(getattr(args, name)).expanduser()
    if args.recap:
        print(ledger.generate_weekly_recap(paths["ledger_db"]))
    elif args.poll or args.watch:
        dispatcher = gateway.ChannelDispatcher("telegram", paths["state_file"].parent / "messaging")
        while True:
            print(json.dumps({"processed_updates": poll_once(dispatcher, paths["ledger_db"])}), flush=True)
            if not args.watch:
                break
    else:
        report = run_pipeline(args.date or local_now().strftime("%Y-%m-%d"), **paths,
                              mock_reply=args.mock_reply, mock_confirmation=args.mock_confirmation,
                              interactive=args.interactive, channel=args.channel,
                              ignore_quiet_hours=args.ignore_quiet_hours)
        print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
