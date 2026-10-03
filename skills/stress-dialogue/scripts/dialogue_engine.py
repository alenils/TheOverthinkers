#!/usr/bin/env python3
"""Cognitive appraisal triage and stress dialogue state machine.

Implements the 4-way appraisal matrix (Eustress, Distress, Recovery Drain, Uncertain),
strictly caps conversational turns (<= 3 turns), enforces the anti-rumination
circuit breaker, and locks in exactly 1 actionable micro-intervention with canonical IDs.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

OPENING_CHECKIN = (
    "Morning. Biometrics show an autonomic dip. "
    "Looking at your day from the outside, what's taking up your bandwidth?"
)

CIRCUIT_BREAKER_INTERVENTION = (
    "Stepping back: observing an emotional loop. Further analysis now reinforces rumination "
    "rather than recovery. Prescribed micro-action: Take 3 physiological sighs (double inhale, "
    "extended exhale) and step away from screens for 5 minutes. Checking back tomorrow."
)

# Canonical Intervention Catalog
INTERVENTIONS = {
    "PHYSIOLOGICAL_SIGH": {
        "id": "PHYSIOLOGICAL_SIGH",
        "description": "Take 3 physiological sighs (double inhale through nose, extended exhale through mouth).",
    },
    "OUTDOOR_WALK": {
        "id": "OUTDOOR_WALK",
        "description": "Take a 10-minute outdoor walk without screens to reset autonomic tone.",
    },
    "PRIORITY_LOCK": {
        "id": "PRIORITY_LOCK",
        "description": "Lock in your single #1 priority milestone this morning and defer secondary threads.",
    },
    "SCREEN_CURFEW": {
        "id": "SCREEN_CURFEW",
        "description": "Protect tonight's recovery window: enforce a hard screen shutdown 45 minutes before sleep.",
    },
    "GROUNDING_PAUSE": {
        "id": "GROUNDING_PAUSE",
        "description": "Take a 5-minute pause without devices to observe and clarify the primary friction point.",
    },
}


def detect_rumination(text: str) -> bool:
    """Detect cyclic, catastrophizing, or ungrounded emotional venting."""
    lower = text.lower()
    markers = [
        "why does this always happen",
        "i can't stop thinking",
        "spiraling",
        "everything is ruined",
        "hopeless",
        "catastrophe",
        "over and over",
        "doomed",
        "i hate everything",
        "what if everything fails",
    ]
    if any(m in lower for m in markers):
        return True
    return False


def classify_appraisal(user_text: str) -> Tuple[str, str, str, str]:
    """Classify user text into the 4-way appraisal matrix with robust threat precedence.

    Returns:
        (category, cause_id, intervention_id, attributed_cause)
    """
    lower = user_text.lower().strip()

    # 1. Check Distress / Threat FIRST to avoid swallowing threat language under work keywords
    distress_markers = [
        "argument", "fight", "conflict", "yelled", "fired", "layoff", "laid off",
        "panic", "anxious", "anxiety", "scared", "worried", "crisis", "boss yelled",
        "threatening", "threatened", "trapped", "terrified", "dread",
    ]
    if any(m in lower for m in distress_markers):
        return (
            "DISTRESS",
            "ACUTE_THREAT",
            "PHYSIOLOGICAL_SIGH",
            "Acute threat or low-control friction",
        )

    # 2. Recovery Drain (poor recovery, chronic sleep deficit, physical exhaustion)
    drain_markers = [
        "tired", "exhausted", "sleep", "insomnia", "wiped out", "drained",
        "burned out", "fatigue", "haven't slept", "sleep deficit",
    ]
    if any(k in lower for k in drain_markers):
        return (
            "RECOVERY_DRAIN",
            "RECOVERY_DEFICIT",
            "SCREEN_CURFEW",
            "Cumulative recovery deficit and fatigue",
        )

    # 3. Eustress (High control / challenge orientation / proactive load)
    eustress_markers = [
        "launch", "release", "shipping", "excited", "code", "deadline",
        "project", "presentation", "interview", "workload", "milestone",
    ]
    high_control_phrases = ["working on", "finishing", "preparing", "building", "executing", "delivering"]
    if any(k in lower for k in eustress_markers) or any(p in lower for p in high_control_phrases):
        return (
            "EUSTRESS",
            "CHALLENGE_LOAD",
            "PRIORITY_LOCK",
            "High-demand challenge milestone",
        )

    # 4. Uncertain / Ambiguous
    words = lower.split()
    if len(words) < 4 or any(u in lower for u in ["not sure", "idk", "dont know", "don't know", "busy", "just stuff", "nothing much"]):
        return (
            "UNCERTAIN",
            "AMBIGUOUS_FRICTION",
            "GROUNDING_PAUSE",
            "Ambiguous friction source",
        )

    # Fallback for general negative or unclassified tension
    return (
        "DISTRESS",
        "UNSPECIFIED_TENSION",
        "OUTDOOR_WALK",
        "Unspecified acute tension",
    )


class DialogueSession:
    """Manages conversational check-in adhering to <= 3 turn bounds."""

    def __init__(
        self,
        anomaly_payload: Dict[str, Any],
        max_turns: int = 3,
    ):
        if max_turns < 2:
            max_turns = 2
        self.anomaly = anomaly_payload
        self.max_turns = max_turns
        self.transcript: List[Dict[str, Any]] = []
        self.turn_count = 0
        self.clarification_asked = False
        self.status = "ACTIVE"
        self.appraisal_category: Optional[str] = None
        self.cause_id: Optional[str] = None
        self.intervention_id: Optional[str] = None
        self.attributed_cause: Optional[str] = None
        self.prescribed_action: Optional[str] = None
        self.subjective_rating: Optional[int] = None

    def start(self) -> str:
        """Turn 1 (Coach): Dispatch opening observer check-in."""
        self.turn_count = 1
        msg = OPENING_CHECKIN
        self.transcript.append({
            "turn": self.turn_count,
            "speaker": "coach",
            "message": msg,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return msg

    def process_user_turn(self, user_text: str, subjective_rating: Optional[int] = None) -> str:
        """Process user message and generate next coach reply or closure."""
        if self.status != "ACTIVE":
            return "Session already concluded."

        if subjective_rating is not None:
            self.subjective_rating = max(1, min(10, subjective_rating))

        self.transcript.append({
            "turn": self.turn_count,
            "speaker": "user",
            "message": user_text,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # Anti-rumination circuit breaker check
        if detect_rumination(user_text):
            self.turn_count += 1
            self.status = "CIRCUIT_BREAKER_TRIGGERED"
            self.appraisal_category = "DISTRESS"
            self.cause_id = "RUMINATION_SPIRAL"
            self.intervention_id = "PHYSIOLOGICAL_SIGH"
            self.attributed_cause = "Rumination spiral"
            self.prescribed_action = INTERVENTIONS["PHYSIOLOGICAL_SIGH"]["description"]
            self.transcript.append({
                "turn": self.turn_count,
                "speaker": "coach",
                "message": CIRCUIT_BREAKER_INTERVENTION,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return CIRCUIT_BREAKER_INTERVENTION

        category, cause_id, int_id, cause_text = classify_appraisal(user_text)

        # Allow exactly 1 clarification when UNCERTAIN and turn headroom permits
        if category == "UNCERTAIN" and not self.clarification_asked and self.turn_count < self.max_turns:
            self.turn_count += 1
            self.clarification_asked = True
            clarifying_msg = (
                "Looking at today from an external viewpoint: is the main friction coming from "
                "an operational workload, an interpersonal conflict, or physical tiredness?"
            )
            self.transcript.append({
                "turn": self.turn_count,
                "speaker": "coach",
                "message": clarifying_msg,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return clarifying_msg

        # Resolve appraisal and commit to 1 micro-action
        self.turn_count += 1
        self.status = "COMPLETED"
        # Preserve UNCERTAIN if user remained ambiguous after clarification!
        self.appraisal_category = category
        self.cause_id = cause_id
        self.intervention_id = int_id
        self.attributed_cause = cause_text
        self.prescribed_action = INTERVENTIONS[int_id]["description"]

        closing_msg = (
            f"Understood. Stepping back to observe the pattern: {self.attributed_cause.lower()}. "
            f"Prescribed micro-action: {self.prescribed_action} "
            f"Check-in complete. Monitoring tomorrow's recovery."
        )
        self.transcript.append({
            "turn": self.turn_count,
            "speaker": "coach",
            "message": closing_msg,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return closing_msg

    def get_summary(self) -> Dict[str, Any]:
        """Return structured session summary suitable for Gate 3 ledger."""
        metric_key = self.anomaly.get("triggered_metric") or self.anomaly.get("metric") or "hrv_score"
        return {
            "status": self.status,
            "date": self.anomaly.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
            "trigger_metric": metric_key,
            "deviation_sigma": self.anomaly.get("deviation_sigma", -1.5),
            "appraisal_category": self.appraisal_category,
            "cause_id": self.cause_id,
            "attributed_cause": self.attributed_cause,
            "intervention_id": self.intervention_id,
            "intervention_type": self.prescribed_action,
            "subjective_rating": self.subjective_rating,
            "turn_count": self.turn_count,
            "max_turns": self.max_turns,
            "transcript": self.transcript,
        }


def run_dialogue(
    anomaly_payload: Dict[str, Any],
    mock_responses: Optional[List[str]] = None,
    interactive: bool = False,
    max_turns: int = 3,
    subjective_rating: Optional[int] = None,
) -> Dict[str, Any]:
    """Run a dialogue session programmatically or interactively."""
    session = DialogueSession(anomaly_payload=anomaly_payload, max_turns=max_turns)
    opening = session.start()

    if interactive:
        print(f"\n[Coach Turn 1]: {opening}")

    resp_idx = 0
    while session.status == "ACTIVE" and session.turn_count <= max_turns:
        if interactive:
            try:
                user_msg = input(f"[User Turn {session.turn_count}]: ").strip()
            except (EOFError, KeyboardInterrupt):
                user_msg = "Exhausted"
        else:
            if mock_responses and resp_idx < len(mock_responses):
                user_msg = mock_responses[resp_idx]
                resp_idx += 1
            else:
                user_msg = "Defaulting to workload release"

        coach_reply = session.process_user_turn(user_msg, subjective_rating=subjective_rating)
        if interactive:
            print(f"[Coach Turn {session.turn_count}]: {coach_reply}")

        if session.status in ["COMPLETED", "CIRCUIT_BREAKER_TRIGGERED"]:
            break

    return session.get_summary()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run cognitive appraisal stress dialogue.")
    parser.add_argument("--anomaly-json", help="JSON string with anomaly payload")
    parser.add_argument("--anomaly-file", help="Path to JSON file with anomaly payload")
    parser.add_argument("--mock-reply", help="Single mock reply string")
    parser.add_argument("--interactive", action="store_true", help="Interactive terminal mode")
    parser.add_argument("--max-turns", type=int, default=3, help="Max turn cap")
    parser.add_argument("--rating", type=int, help="Optional subjective rating (1-10)")
    parser.add_argument("--output", help="Path to save result summary JSON")

    args = parser.parse_args()

    payload: Dict[str, Any] = {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "triggered_metric": "hrv_score",
        "deviation_sigma": -1.8,
    }
    if args.anomaly_json:
        payload.update(json.loads(args.anomaly_json))
    elif args.anomaly_file:
        payload.update(json.loads(Path(args.anomaly_file).read_text(encoding="utf-8")))

    mock_list = [args.mock_reply] if args.mock_reply else None
    summary = run_dialogue(
        anomaly_payload=payload,
        mock_responses=mock_list,
        interactive=args.interactive,
        max_turns=args.max_turns,
        subjective_rating=args.rating,
    )

    if args.output:
        out_p = Path(args.output)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
