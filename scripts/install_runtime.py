#!/usr/bin/env python3
"""Hermes Runtime Installer for The Overthinkers.

Bootstraps the runtime environment outside the git checkout:
  - Validates Python >= 3.11
  - Installs skills into $HERMES_HOME/skills/
  - Scaffolds $HERMES_HOME/Profile/ preserving existing personalized files
  - Initializes storage paths for biometric DBs, ledger, and concurrency locks
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import sys
from typing import Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def check_environment() -> None:
    """Validate python version and system dependencies."""
    if sys.version_info < (3, 11):
        raise RuntimeError(f"Python >= 3.11 required; currently running {sys.version}")


def get_default_runtime_dir() -> Path:
    """Resolve default runtime directory from environment or fallback."""
    env_home = os.environ.get("HERMES_HOME")
    if env_home:
        return Path(env_home).expanduser()
    return Path.home() / ".hermes"


def install_runtime(
    dest_dir: Path,
    dry_run: bool = False,
) -> Dict[str, List[str]]:
    """Install skills and scaffold runtime directories without overwriting personal files."""
    check_environment()

    report: Dict[str, List[str]] = {
        "created_dirs": [],
        "installed_skills": [],
        "scaffolded_profiles": [],
        "preserved_profiles": [],
    }

    skills_src = PROJECT_ROOT / "skills"
    profiles_src = PROJECT_ROOT / "Profile"

    skills_dest = dest_dir / "skills"
    profiles_dest = dest_dir / "Profile"
    data_dest = dest_dir / "data"
    state_dest = dest_dir / "state"

    dirs_to_create = [dest_dir, skills_dest, profiles_dest, data_dest, state_dest]
    for d in dirs_to_create:
        if not d.is_dir():
            if not dry_run:
                d.mkdir(parents=True, exist_ok=True)
            report["created_dirs"].append(str(d))

    # 1. Install skills
    if skills_src.is_dir():
        for sk_dir in sorted(skills_src.iterdir()):
            if sk_dir.is_dir() and (sk_dir / "SKILL.md").is_file():
                target_sk = skills_dest / sk_dir.name
                if not dry_run:
                    if target_sk.exists():
                        shutil.rmtree(target_sk)
                    shutil.copytree(sk_dir, target_sk)
                report["installed_skills"].append(sk_dir.name)

    # 2. Scaffold Profile files (preserving existing personal files!)
    if profiles_src.is_dir():
        for p_file in sorted(profiles_src.iterdir()):
            if p_file.is_file() and p_file.name.endswith(".md"):
                target_p = profiles_dest / p_file.name
                if target_p.is_file():
                    report["preserved_profiles"].append(p_file.name)
                else:
                    if not dry_run:
                        shutil.copy2(p_file, target_p)
                    report["scaffolded_profiles"].append(p_file.name)

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Install The Overthinkers Hermes runtime.")
    parser.add_argument("--dest", help="Target runtime directory (default: $HERMES_HOME or ~/.hermes)")
    parser.add_argument("--local", action="store_true", help="Install into local .runtime directory")
    parser.add_argument("--dry-run", action="store_true", help="Simulate installation without changes")

    args = parser.parse_args()

    if args.local:
        dest = PROJECT_ROOT / ".runtime"
    elif args.dest:
        dest = Path(args.dest).expanduser()
    else:
        dest = get_default_runtime_dir()

    print(f"Installing The Overthinkers runtime into: {dest}")
    res = install_runtime(dest, dry_run=args.dry_run)

    print(f"Created directories: {len(res['created_dirs'])}")
    print(f"Installed skills: {', '.join(res['installed_skills'])}")
    print(f"Scaffolded profiles: {', '.join(res['scaffolded_profiles'])}")
    if res["preserved_profiles"]:
        print(f"Preserved existing personal profiles: {', '.join(res['preserved_profiles'])}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
