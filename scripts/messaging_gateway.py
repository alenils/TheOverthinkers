#!/usr/bin/env python3
"""Durable Telegram delivery and explicit local mock transport.

Journal sends before HTTP; unknown delivery is never retried automatically.
Run only one poller per bot (Telegram getUpdates contract).
"""
from __future__ import annotations
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from urllib.request import Request, urlopen
import uuid
from runtime_config import runtime_home

if os.name == "nt":
    import msvcrt
else:
    import fcntl

DEFAULT_TTL_SECONDS = 3600


class ConcurrencyLock:
    def __init__(self, lock_path: Path):
        self.lock_path = lock_path
        self._fd = None

    def __enter__(self):
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._fd = os.open(str(self.lock_path), os.O_CREAT | os.O_RDWR)
        if os.name == "nt":
            if os.fstat(self._fd).st_size == 0:
                os.write(self._fd, b"0")
            os.lseek(self._fd, 0, os.SEEK_SET)
            msvcrt.locking(self._fd, msvcrt.LK_LOCK, 1)
        else:
            fcntl.flock(self._fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, *args):
        if self._fd is not None:
            try:
                if os.name == "nt":
                    os.lseek(self._fd, 0, os.SEEK_SET)
                    msvcrt.locking(self._fd, msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(self._fd, fcntl.LOCK_UN)
            finally:
                os.close(self._fd)
                self._fd = None


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    tmp.replace(path)


class TelegramTransport:
    """Private-chat transport; secrets and recipient IDs come from environment."""
    def __init__(self, token: str, chat_id: str, user_id: str, opener=urlopen):
        if not token or not chat_id or not user_id:
            raise ValueError("Set TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID and TELEGRAM_USER_ID")
        self._token, self.chat_id, self.user_id = token, str(chat_id), str(user_id)
        self._opener = opener

    @classmethod
    def from_env(cls):
        return cls(*(os.environ.get(key, "") for key in
                     ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "TELEGRAM_USER_ID")))

    def request(self, method: str, payload: dict):
        req = Request(f"https://api.telegram.org/bot{self._token}/{method}",
                      data=json.dumps(payload).encode(),
                      headers={"Content-Type": "application/json"})
        try:
            with self._opener(req, timeout=35) as response:
                result = json.load(response)
            if not result.get("ok"):
                raise RuntimeError("Telegram rejected the request")
            return result["result"]
        except Exception:
            raise RuntimeError("Telegram request failed; inspect private runtime delivery state") from None

    def send(self, text: str) -> int:
        return self.request("sendMessage", {
            "chat_id": self.chat_id, "text": text,
            "reply_markup": {"force_reply": True, "selective": True},
        })["message_id"]

    def updates(self, offset: int):
        return self.request("getUpdates", {"offset": offset, "timeout": 20,
                                           "allowed_updates": ["message"]})


class MessageEvent:
    def __init__(self, **fields):
        self.__dict__.update(fields)

    def to_dict(self):
        return dict(self.__dict__)


class ChannelDispatcher:
    def __init__(self, channel="mock", spool_dir=None,
                 reply_ttl_seconds=DEFAULT_TTL_SECONDS, transport=None):
        if channel not in ("mock", "hermes_cli", "telegram"):
            raise ValueError("Supported channels: mock, telegram")
        self.channel = "mock" if channel == "hermes_cli" else channel
        self.transport = transport
        if self.channel == "telegram" and transport is None:
            self.transport = TelegramTransport.from_env()
        self.spool_dir = Path(spool_dir) if spool_dir else runtime_home() / "state" / "messaging"
        self.spool_dir.mkdir(parents=True, exist_ok=True)
        self.reply_ttl_seconds = reply_ttl_seconds

    def session_file(self, session_id):
        if not re.fullmatch(r"[A-Za-z0-9_-]+", session_id):
            raise ValueError("Invalid session ID")
        return self.spool_dir / f"session_{session_id}.json"

    def load(self, session_id):
        return json.loads(self.session_file(session_id).read_text(encoding="utf-8"))

    def save(self, data):
        save_json(self.session_file(data["session_id"]), data)

    def format_outbound_text(self, text, is_simulated=False):
        if is_simulated and not text.startswith("[Simulated Alert]"):
            return f"[Simulated Alert] {text}"
        return text

    def dispatch(self, text, session_id=None, is_simulated=False,
                 event_id=None, context=None) -> MessageEvent:
        session_id = session_id or str(uuid.uuid4())
        event_id = event_id or f"evt_{uuid.uuid4().hex}"
        with ConcurrencyLock(self.spool_dir / ".delivery.lock"):
            path = self.session_file(session_id)
            data = self.load(session_id) if path.exists() else {
                "session_id": session_id, "events": [], "context": context or {},
                "created_at": datetime.now(timezone.utc).isoformat(),
                "ttl_seconds": self.reply_ttl_seconds, "status": "AWAITING_REPLY",
                "chat_id": getattr(self.transport, "chat_id", None),
                "user_id": getattr(self.transport, "user_id", None),
            }
            for previous in data["events"]:
                if previous["event_id"] == event_id:
                    return MessageEvent(**previous)
            event = MessageEvent(event_id=event_id, session_id=session_id,
                                 direction="OUTBOUND", text=self.format_outbound_text(text, is_simulated),
                                 channel=self.channel, timestamp=datetime.now(timezone.utc).isoformat(),
                                 correlation_id=None, is_simulated=is_simulated,
                                 delivery_status="SENDING", message_id=None)
            data["events"].append(event.to_dict())
            data["status"] = "SENDING"
            self.save(data)
            try:
                event.message_id = self.transport.send(event.text) if self.transport else None
                event.delivery_status = "DELIVERED" if self.transport else "MOCK_RECORDED"
                data["status"] = "AWAITING_REPLY"
                data["awaiting_since"] = event.timestamp
            except Exception:
                event.delivery_status = "DELIVERY_UNCERTAIN"
                data["status"] = "DELIVERY_UNCERTAIN"
                data["events"][-1] = event.to_dict()
                self.save(data)
                raise
            data["events"][-1] = event.to_dict()
            self.save(data)
            return event

    def record_reply(self, session_id, reply_text, event_id=None):
        with ConcurrencyLock(self.spool_dir / ".delivery.lock"):
            if not reply_text.strip():
                raise ValueError("An empty input is not a reply")
            data = self.load(session_id)
            event_id = event_id or f"evt_{uuid.uuid4().hex}"
            if any(e["event_id"] == event_id for e in data["events"]):
                return None
            status = self._check_session_status(session_id)
            if status == "EXPIRED_NO_REPLY":
                raise TimeoutError("Session reply deadline elapsed")
            if status not in ("AWAITING_REPLY", "AWAITING_CONFIRMATION"):
                raise ValueError("Session is not awaiting a reply")
            outbound = next(e for e in reversed(data["events"]) if e["direction"] == "OUTBOUND")
            event = MessageEvent(event_id=event_id, session_id=session_id, direction="INBOUND",
                                 text=reply_text, channel=self.channel,
                                 timestamp=datetime.now(timezone.utc).isoformat(),
                                 correlation_id=outbound["event_id"], is_simulated=outbound["is_simulated"])
            data["events"].append(event.to_dict())
            data["status"] = "REPLY_RECEIVED"
            self.save(data)
            return event

    def check_session_status(self, session_id):
        with ConcurrencyLock(self.spool_dir / ".delivery.lock"):
            return self._check_session_status(session_id)

    def _check_session_status(self, session_id):
        if not self.session_file(session_id).is_file():
            return "NOT_FOUND"
        data = self.load(session_id)
        if data["status"] == "SENDING":
            data["status"] = "DELIVERY_UNCERTAIN"
            self.save(data)
        if data["status"] in ("AWAITING_REPLY", "AWAITING_CONFIRMATION"):
            since = datetime.fromisoformat(data.get("awaiting_since", data["created_at"]))
            if (datetime.now(timezone.utc) - since).total_seconds() > data["ttl_seconds"]:
                data["status"] = "EXPIRED_NO_REPLY"
                self.save(data)
        return data["status"]

    def correlate_update(self, update):
        msg = update.get("message", {})
        if (str(msg.get("chat", {}).get("id")) != self.transport.chat_id
                or str(msg.get("from", {}).get("id")) != self.transport.user_id
                or msg.get("chat", {}).get("type") != "private"
                or not msg.get("text", "").strip()):
            return None
        reply_to = msg.get("reply_to_message", {}).get("message_id")
        for path in self.spool_dir.glob("session_*.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            if data["chat_id"] != self.transport.chat_id or data["user_id"] != self.transport.user_id:
                continue
            status = self.check_session_status(data["session_id"])
            outbound = next((e for e in reversed(data["events"]) if e["direction"] == "OUTBOUND"), {})
            if (reply_to is not None and outbound.get("message_id") == reply_to
                    and status in ("AWAITING_REPLY", "AWAITING_CONFIRMATION", "REPLY_RECEIVED")):
                return data["session_id"], msg["text"], f"telegram_{update['update_id']}"
        return None
