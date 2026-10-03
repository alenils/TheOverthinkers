#!/usr/bin/env python3
"""Gate 0 Steel Thread — Mock Anomaly Trigger & Observer Dialogue Simulation.

Dispatches an outbound check-in using 3rd-person self-distanced observer framing,
captures user response, provides a concise 1-action closure, and terminates
within <= 2 conversational turns.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from typing import Any, Dict, List

DEFAULT_OPENING = (
    "Morning. Biometrics show an autonomic dip. "
    "Looking at your day from the outside, what's taking up your bandwidth?"
)

CIRCUIT_BREAKER_MSG = (
    "Stepping back: we are observing an open-ended loop. Additional analysis right now "
    "reinforces rumination rather than recovery. Prescribed micro-action: "
    "Take 3 physiological sighs and execute the single priority task. "
    "Let the data evaluate tomorrow morning."
)


def resolve_project_root() -> Path:
    """Find repository root relative to this script."""
    return Path(__file__).resolve().parent.parent


def load_profile(profile_dir: Path) -> Dict[str, str]:
    """Load profile documents and fail loudly if mandatory tiers are missing."""
    if not profile_dir.is_dir():
        raise FileNotFoundError(f"Profile directory not found: {profile_dir}")

    required = ["SOUL.md", "USER.md", "MEMORY.md"]
    profile_data: Dict[str, str] = {}
    for doc in required:
        p = profile_dir / doc
        if not p.is_file():
            raise FileNotFoundError(f"Mandatory profile document missing: {p}")
        content = p.read_text(encoding="utf-8")
        if not content.strip():
            raise ValueError(f"Profile document is empty: {p}")
        profile_data[doc] = content

    return profile_data


def check_quiet_hours(dt: datetime, quiet_hours: str = "08:00-21:00") -> bool:
    """Return True if dt time is within the allowed proactive ping window."""
    m = re.match(r"^(\d{2}):(\d{2})-(\d{2}):(\d{2})$", quiet_hours.strip())
    if not m:
        return True  # fallback if malformed
    start_h, start_m, end_h, end_m = map(int, m.groups())
    t = dt.time()
    start_time = datetime.min.time().replace(hour=start_h, minute=start_m)
    end_time = datetime.min.time().replace(hour=end_h, minute=end_m)

    if start_time <= end_time:
        return start_time <= t <= end_time
    # Window spans midnight
    return t >= start_time or t <= end_time


def check_daily_dispatch(state_path: Path, date_str: str) -> bool:
    """Ensure at most one proactive check-in is dispatched per day."""
    if not state_path.is_file():
        return True
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
        dispatched_dates = data.get("dispatched_dates", [])
        return date_str not in dispatched_dates
    except Exception:
        return True


def record_dispatch(state_path: Path, date_str: str) -> None:
    """Record a dispatched check-in for idempotency."""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    data: Dict[str, Any] = {"dispatched_dates": []}
    if state_path.is_file():
        try:
            data = json.loads(state_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    if date_str not in data.setdefault("dispatched_dates", []):
        data["dispatched_dates"].append(date_str)
    state_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def detect_rumination(text: str) -> bool:
    """Flag repetitive catastrophic or circular venting."""
    lower = text.lower()
    rumination_keywords = [
        "why does this always happen",
        "i can't stop thinking",
        "spiraling",
        "everything is ruined",
        "hopeless",
        "catastrophe",
        "over and over",
        "what if everything fails",
    ]
    if any(k in lower for k in rumination_keywords):
        return True
    # Count first-person immersion signals
    i_tokens = len(re.findall(r"\b(i|me|my|myself)\b", lower))
    if i_tokens >= 8:
        return True
    return False


def generate_observer_reply(user_text: str, soul_content: str | None = None) -> str:
    """Generate a concise, self-distanced acknowledgment and single micro-action."""
    if detect_rumination(user_text):
        return CIRCUIT_BREAKER_MSG

    text = user_text.lower()
    if any(k in text for k in ["deadline", "deliverable", "launch", "project", "work", "task", "code"]):
        action = "Lock in your single highest-priority milestone for this morning and defer secondary threads."
    elif any(k in text for k in ["argument", "fight", "conflict", "meeting", "boss", "client"]):
        action = "Take 3 physiological sighs before entering the discussion to regulate autonomic tone."
    elif any(k in text for k in ["tired", "sleep", "exhausted", "fatigue", "sick", "ill"]):
        action = "Protect tonight's recovery window: enforce a hard screen shutdown 45 minutes before sleep."
    else:
        action = "Take a 10-minute walk without your phone to step outside the problem and reset your perspective."

    return (
        f"Understood. Stepping back to observe the pattern: the body is responding to immediate load. "
        f"Prescribed micro-action: {action} "
        f"Checking back in tomorrow morning to evaluate recovery."
    )


def run_session(
    anomaly_data: Dict[str, Any],
    mock_reply: str | None = None,
    interactive: bool = False,
    profile_dir: Path | None = None,
    state_file: Path | None = None,
    ignore_quiet_hours: bool = False,
    ignore_daily_limit: bool = False,
) -> Dict[str, Any]:
    """Execute the <= 2 turn observer dialogue loop with profile and boundary checks."""
    root = resolve_project_root()
    p_dir = profile_dir if profile_dir is not None else (root / "Profile")
    profile = load_profile(p_dir)

    now = datetime.now(timezone.utc)
    date_str = anomaly_data.get("date", now.strftime("%Y-%m-%d"))

    # 1. Quiet Hours Enforcement
    if not ignore_quiet_hours:
        allowed = check_quiet_hours(now, quiet_hours="08:00-21:00")
        if not allowed:
            return {
                "status": "SUPPRESSED_QUIET_HOURS",
                "reason": "Outside allowed proactive ping window (08:00-21:00)",
                "date": date_str,
            }

    # 2. Silence by default / once-per-day enforcement
    s_path = state_file if state_file is not None else (root / ".state" / "dispatch_state.json")
    if not ignore_daily_limit:
        if not check_daily_dispatch(s_path, date_str):
            return {
                "status": "SUPPRESSED_ALREADY_DISPATCHED",
                "reason": f"Proactive check-in already dispatched for {date_str}",
                "date": date_str,
            }

    turns: List[Dict[str, str]] = []

    # Turn 1: Outbound check-in
    turn1_msg = DEFAULT_OPENING
    turns.append({"turn": 1, "speaker": "coach", "message": turn1_msg})

    if interactive:
        print(f"[Coach Turn 1]: {turn1_msg}")
        try:
            user_input = input("[User Response]: ").strip()
        except (EOFError, KeyboardInterrupt):
            user_input = ""
    else:
        user_input = (
            mock_reply.strip()
            if mock_reply is not None
            else "I have a major deadline today and three back-to-back reviews."
        )

    turns.append({"turn": 1, "speaker": "user", "message": user_input})

    # Turn 2: Concise observer acknowledgment + single micro-action
    turn2_msg = generate_observer_reply(user_input, soul_content=profile.get("SOUL.md"))
    turns.append({"turn": 2, "speaker": "coach", "message": turn2_msg})

    if interactive:
        print(f"[Coach Turn 2]: {turn2_msg}")
        print("[Session Terminated — Hard turn cap reached]")

    # Record dispatch upon successful completion
    if not ignore_daily_limit:
        record_dispatch(s_path, date_str)

    result: Dict[str, Any] = {
        "status": "TERMINATED",
        "turn_count": 2,
        "max_turns": 2,
        "timestamp": now.isoformat(),
        "anomaly": anomaly_data,
        "profile_loaded": list(profile.keys()),
        "transcript": turns,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Simulate Gate 0 steel thread check-in.")
    parser.add_argument("--metric", default="hrv_deviation", help="Triggering metric name")
    parser.add_argument("--deviation", type=float, default=-1.8, help="Deviation sigma")
    parser.add_argument("--date", default=None, help="Target date YYYY-MM-DD")
    parser.add_argument("--mock-reply", default=None, help="Mock user reply text")
    parser.add_argument("--interactive", action="store_true", help="Interactive terminal mode")
    parser.add_argument("--json", action="store_true", help="Print JSON result to stdout")
    parser.add_argument("--output", default=None, help="Save transcript JSON to path")
    parser.add_argument("--profile-dir", default=None, help="Path to Profile directory")
    parser.add_argument("--state-file", default=None, help="Path to dispatch state file")
    parser.add_argument("--ignore-quiet-hours", action="store_true", default=True, help="Bypass quiet hours check")
    parser.add_argument("--ignore-daily-limit", action="store_true", default=False, help="Bypass once-per-day check")

    args = parser.parse_args()

    date_val = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    anomaly = {
        "date": date_val,
        "metric": args.metric,
        "deviation_sigma": args.deviation,
        "triggered_at": datetime.now(timezone.utc).isoformat(),
    }

    profile_path = Path(args.profile_dir) if args.profile_dir else None
    state_path = Path(args.state_file) if args.state_file else None

    session_result = run_session(
        anomaly_data=anomaly,
        mock_reply=args.mock_reply,
        interactive=args.interactive,
        profile_dir=profile_path,
        state_file=state_path,
        ignore_quiet_hours=args.ignore_quiet_hours,
        ignore_daily_limit=args.ignore_daily_limit,
    )

    if args.output:
        out_p = Path(args.output)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(json.dumps(session_result, indent=2), encoding="utf-8")

    if args.json or not args.interactive:
        print(json.dumps(session_result, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
