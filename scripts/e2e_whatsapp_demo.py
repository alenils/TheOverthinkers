#!/usr/bin/env python3
"""End-to-End WhatsApp Demo Runner for The Overthinkers on Hermes / Matrix.

Coordinates:
  1. Checks WhatsApp pairing credentials and gateway status
  2. Dispatches Gate 0 simulated morning check-in to WhatsApp
  3. Monitors and logs conversational turn completion
  4. Records the check-in into the closed-loop outcome ledger
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Dict, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "skills" / "stress-ledger" / "scripts"))

import ledger  # noqa: E402
import messaging_gateway  # noqa: E402


def check_pairing_status() -> bool:
    """Check whether WhatsApp credentials exist in Hermes session directory."""
    hermes_home = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
    session_creds = hermes_home / "whatsapp" / "session" / "creds.json"
    platform_creds = hermes_home / "platforms" / "whatsapp" / "session" / "creds.json"
    return session_creds.is_file() or platform_creds.is_file()


def send_whatsapp_checkin(recipient: str, message: str) -> bool:
    """Send an outbound message to WhatsApp using hermes send."""
    cmd = ["hermes", "send", "--to", f"whatsapp:{recipient}", message]
    print(f"Dispatching via Hermes: {' '.join(cmd)}")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if proc.returncode == 0:
            print("✓ Check-in dispatched successfully to WhatsApp.")
            return True
        print(f"✗ Failed to dispatch via hermes send: {proc.stderr.strip()}", file=sys.stderr)
        return False
    except Exception as exc:
        print(f"✗ Error dispatching message: {exc}", file=sys.stderr)
        return False


def run_e2e_demo(recipient: str, ledger_db: Path = Path("data/ledger.db")) -> Dict[str, Any]:
    """Execute the end-to-end WhatsApp check-in flow."""
    print(f"\n=======================================================")
    print(f"  The Overthinkers — End-to-End WhatsApp Demo")
    print(f"  Recipient: +{recipient}")
    print(f"=======================================================\n")

    is_paired = check_pairing_status()
    if not is_paired:
        print("⚠ WhatsApp is not yet paired on this machine!")
        print("  Please run: ~/overthinkers/scripts/pair_whatsapp.sh")
        print("  and scan the QR code with WhatsApp on your phone first.\n")
        return {"status": "NOT_PAIRED", "recipient": recipient}

    dispatcher = messaging_gateway.ChannelDispatcher(channel="whatsapp", recipient=recipient)
    opening_text = (
        "[Simulated Alert] Morning. Biometrics indicate an autonomic dip. "
        "Looking at your day from the outside, what's taking up your bandwidth?"
    )

    now_iso = datetime.now(timezone.utc).isoformat()
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Step 1: Dispatch to WhatsApp
    print("Step 1: Sending simulated autonomic check-in to your WhatsApp...")
    event = dispatcher.dispatch(opening_text, is_simulated=True)
    sent_ok = send_whatsapp_checkin(recipient, event.text)

    # Step 2: Record in Outcome Ledger
    entry_id = ledger.add_ledger_entry(
        db_path=ledger_db,
        trigger_metric="hrv_score",
        attributed_cause="E2E WhatsApp Demonstration Check-In",
        intervention_type="Awaiting user WhatsApp response",
        date_str=today_str,
        deviation_sigma=-1.8,
        cause_id="PENDING_APPRAISAL",
        intervention_id="PENDING",
    )
    print(f"Step 2: Logged pending check-in #{entry_id} in {ledger_db}")

    print("\n-------------------------------------------------------")
    print("📱 Next Steps:")
    print("1. Check WhatsApp on your phone for the message from Hermes.")
    print("2. Reply with your current stress or workload context.")
    print("3. Hermes will evaluate perceived control and reply with 1 micro-action.")
    print("-------------------------------------------------------\n")

    return {
        "status": "DISPATCHED" if sent_ok else "DISPATCH_FAILED",
        "entry_id": entry_id,
        "recipient": recipient,
        "session_id": event.session_id,
        "dispatched_at": now_iso,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run E2E WhatsApp Demo.")
    parser.add_argument("--recipient", default=os.environ.get("USER_WHATSAPP_PHONE"), help="Recipient phone number (digits with country code, e.g. 370...)")
    parser.add_argument("--ledger-db", default="data/ledger.db", help="Path to ledger DB")

    args = parser.parse_args()
    if not args.recipient:
        print("Error: Specify --recipient or export USER_WHATSAPP_PHONE", file=sys.stderr)
        return 2

    res = run_e2e_demo(args.recipient, Path(args.ledger_db))
    print(json.dumps(res, indent=2))
    return 0 if res["status"] in ("DISPATCHED", "NOT_PAIRED") else 1


if __name__ == "__main__":
    sys.exit(main())
