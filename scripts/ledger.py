#!/usr/bin/env python3
"""Convenience CLI forwarder for skills/stress-ledger/scripts/ledger.py."""

import importlib.util
from pathlib import Path
import sys

SKILL_SCRIPT = Path(__file__).resolve().parent.parent / "skills" / "stress-ledger" / "scripts" / "ledger.py"

spec = importlib.util.spec_from_file_location("stress_ledger_mod", str(SKILL_SCRIPT))
if spec is None or spec.loader is None:
    raise ImportError(f"Could not load {SKILL_SCRIPT}")
_mod = importlib.util.module_from_spec(spec)
sys.modules["stress_ledger_mod"] = _mod
spec.loader.exec_module(_mod)

# Export all symbols from stress_ledger_mod into current module
for name in dir(_mod):
    if not name.startswith("__"):
        globals()[name] = getattr(_mod, name)

if __name__ == "__main__":
    sys.exit(_mod.main())
