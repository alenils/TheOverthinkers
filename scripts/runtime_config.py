"""Shared private runtime paths; repository Profile files are templates only."""
import os
from pathlib import Path


def runtime_home() -> Path:
    return Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()


def runtime_paths() -> dict[str, Path]:
    base = runtime_home()
    return {
        "health_db": base / "data" / "health.db",
        "garmin_db": base / "data" / "garmin.db",
        "ledger_db": base / "data" / "ledger.db",
        "memory_path": base / "memories" / "MEMORY.md",
        "state_file": base / "state" / "dispatch_state.json",
    }
