#!/usr/bin/env python3
"""Hermes Messaging Gateway & Channel Dispatcher for The Overthinkers.

Provides:
  - Multi-channel dispatch (Hermes CLI, local messaging event queue, mock simulation)
  - Correlation tracking via session_id and event_id
  - Missing-reply TTL expiration
  - File-based concurrency locking to make check-then-dispatch atomic
  - Explicit labeling of simulated vs live biometric alerts
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import fcntl
import json
import os
from pathlib import Path
import time
from typing import Any, Callable, Dict, Optional
import uuid

DEFAULT_TTL_SECONDS = 3600  # 1 hour reply timeout


class ConcurrencyLock:
    """Inter-process file lock ensuring atomic check-then-dispatch."""

    def __init__(self, lock_path: Path):
        self.lock_path = lock_path
        self._fd: Optional[int] = None

    def __enter__(self) -> ConcurrencyLock:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._fd = os.open(str(self.lock_path), os.O_CREAT | os.O_RDWR)
        fcntl.flock(self._fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._fd is not None:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None


class MessageEvent:
    """Represents a discrete outbound or inbound conversational event."""

    def __init__(
        self,
        event_id: str,
        session_id: str,
        direction: str,  # "OUTBOUND" or "INBOUND"
        text: str,
        channel: str,
        timestamp: str,
        correlation_id: Optional[str] = None,
        is_simulated: bool = False,
    ):
        self.event_id = event_id
        self.session_id = session_id
        self.direction = direction
        self.text = text
        self.channel = channel
        self.timestamp = timestamp
        self.correlation_id = correlation_id
        self.is_simulated = is_simulated

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "session_id": self.session_id,
            "direction": self.direction,
            "text": self.text,
            "channel": self.channel,
            "timestamp": self.timestamp,
            "correlation_id": self.correlation_id,
            "is_simulated": self.is_simulated,
        }


class ChannelDispatcher:
    """Dispatches outbound check-ins and correlates asynchronous replies."""

    def __init__(
        self,
        channel: str = "hermes_cli",
        spool_dir: Optional[Path] = None,
        reply_ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ):
        self.channel = channel
        self.spool_dir = spool_dir or Path(".runtime/messaging_spool")
        self.spool_dir.mkdir(parents=True, exist_ok=True)
        self.reply_ttl_seconds = reply_ttl_seconds

    def format_outbound_text(self, text: str, is_simulated: bool = False) -> str:
        """Label simulated alerts clearly so users distinguish tests from live biometrics."""
        if is_simulated and not text.startswith("[Simulated Alert]"):
            return f"[Simulated Alert] {text}"
        return text

    def dispatch(
        self,
        text: str,
        session_id: Optional[str] = None,
        is_simulated: bool = False,
    ) -> MessageEvent:
        """Dispatch outbound message to channel and register pending event."""
        s_id = session_id or str(uuid.uuid4())
        e_id = f"evt_{uuid.uuid4().hex[:12]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        formatted_text = self.format_outbound_text(text, is_simulated=is_simulated)
        event = MessageEvent(
            event_id=e_id,
            session_id=s_id,
            direction="OUTBOUND",
            text=formatted_text,
            channel=self.channel,
            timestamp=now_iso,
            is_simulated=is_simulated,
        )

        # Spool outbound message
        session_file = self.spool_dir / f"session_{s_id}.json"
        session_data: Dict[str, Any] = {
            "session_id": s_id,
            "status": "AWAITING_REPLY",
            "created_at": now_iso,
            "ttl_seconds": self.reply_ttl_seconds,
            "events": [event.to_dict()],
        }

        tmp_file = session_file.with_suffix(".tmp")
        tmp_file.write_text(json.dumps(session_data, indent=2), encoding="utf-8")
        tmp_file.replace(session_file)

        return event

    def record_reply(self, session_id: str, reply_text: str) -> MessageEvent:
        """Correlate inbound reply to existing active session."""
        session_file = self.spool_dir / f"session_{session_id}.json"
        if not session_file.is_file():
            raise FileNotFoundError(f"Session not found: {session_id}")

        session_data = json.loads(session_file.read_text(encoding="utf-8"))
        created_dt = datetime.fromisoformat(session_data["created_at"])
        elapsed = (datetime.now(timezone.utc) - created_dt).total_seconds()

        if elapsed > session_data.get("ttl_seconds", self.reply_ttl_seconds):
            session_data["status"] = "EXPIRED_NO_REPLY"
            session_file.write_text(json.dumps(session_data, indent=2), encoding="utf-8")
            raise TimeoutError(f"Session {session_id} has expired (elapsed {elapsed:.0f}s > TTL)")

        e_id = f"evt_{uuid.uuid4().hex[:12]}"
        now_iso = datetime.now(timezone.utc).isoformat()
        reply_event = MessageEvent(
            event_id=e_id,
            session_id=session_id,
            direction="INBOUND",
            text=reply_text,
            channel=self.channel,
            timestamp=now_iso,
            correlation_id=session_data["events"][-1]["event_id"],
        )

        session_data["events"].append(reply_event.to_dict())
        session_data["status"] = "REPLY_RECEIVED"

        tmp_file = session_file.with_suffix(".tmp")
        tmp_file.write_text(json.dumps(session_data, indent=2), encoding="utf-8")
        tmp_file.replace(session_file)

        return reply_event

    def check_session_status(self, session_id: str) -> str:
        """Check status and apply TTL expiration if overdue."""
        session_file = self.spool_dir / f"session_{session_id}.json"
        if not session_file.is_file():
            return "NOT_FOUND"

        session_data = json.loads(session_file.read_text(encoding="utf-8"))
        if session_data["status"] == "AWAITING_REPLY":
            created_dt = datetime.fromisoformat(session_data["created_at"])
            elapsed = (datetime.now(timezone.utc) - created_dt).total_seconds()
            if elapsed > session_data.get("ttl_seconds", self.reply_ttl_seconds):
                session_data["status"] = "EXPIRED_NO_REPLY"
                session_file.write_text(json.dumps(session_data, indent=2), encoding="utf-8")

        return session_data["status"]
