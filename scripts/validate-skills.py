#!/usr/bin/env python3
"""Structural validation for Hermes skills — the complement to the leak gate.

Verifies:
  - YAML frontmatter parses, includes name, description, license
  - Skill name matches parent directory name
  - No duplicate skill names across the repository
  - Local references to scripts/ and references/ resolve
  - Every metadata.hermes.config key used is declared
  - Python scripts compile without syntax errors
  - No unresolved fill-in tokens (<YOUR_*>) in published skill content
  - Relative links in root documentation resolve

Usage: python3 scripts/validate-skills.py [--installed] [root]
"""

import os
import pathlib
import re
import subprocess
import sys
import urllib.parse

INSTALLED = "--installed" in sys.argv
_args = [a for a in sys.argv[1:] if not a.startswith("--")]
root = pathlib.Path(_args[0] if _args else ".")
problems, checked = [], 0

SUPPORT_DIRS = {"references", "templates", "assets", "scripts",
                "__pycache__", ".git", ".archive"}

SUBSTITUTION_CLASS = re.compile(
    r"<(YOUR_HEALTH_DIR|YOUR_BASELINE_DOC|YOUR_HEALTH_DB|YOUR_TRAINING_PLAN|"
    r"YOUR_DESIGN_DOC|YOUR_PROMPT|YOUR_PROFILE_NAME|YOUR_PRIVATE_REPO|"
    r"YOUR_GIVEN_NAME|YOUR_FAMILY_NAME|YOUR_GITHUB_HANDLE|USER|PLACEHOLDER)>"
)

REDACTION_TOKEN = r"<(?:value|VALUE|YOUR_[A-Z_]+)>"
CORRUPT_VALUE_RE = re.compile(
    REDACTION_TOKEN + r"(?=[\d%→–]|-\d)" + r"|" + r"(?<=[\d%→–-])" + REDACTION_TOKEN
)

_HERMES_VAR = r"(?:\$\{HERMES_HOME[^}]*\}|\$HERMES_HOME)"
INSTALL_ROOT_RE = re.compile(_HERMES_VAR + r"/(?:" + _HERMES_VAR + r"/)?skills/")
CONFIG_KEY_RE = re.compile(r"(?<![\w./-])((?:health|proactive|stress)\.[a-z_]+)\b")


def iter_skills(base: pathlib.Path):
    skills_root = base / "skills"
    if not skills_root.is_dir():
        return
    for dirpath, dirnames, filenames in os.walk(skills_root, followlinks=True):
        dirnames[:] = sorted(d for d in dirnames if d not in SUPPORT_DIRS)
        if "SKILL.md" not in filenames:
            continue
        p = pathlib.Path(dirpath) / "SKILL.md"
        rel = p.relative_to(skills_root)
        yield p, len(rel.parts) - 1


names_seen = {}
for sk, depth in iter_skills(root):
    checked += 1
    skill_dir, rel = sk.parent, sk.relative_to(root)
    text = sk.read_text(encoding="utf-8")

    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        problems.append(f"{rel}: missing frontmatter")
        continue

    fm = m.group(1)
    name = re.search(r"^name:\s*(\S+)", fm, re.M)
    if not name:
        problems.append(f"{rel}: frontmatter missing 'name'")
    else:
        if not INSTALLED and name.group(1) != skill_dir.name:
            problems.append(f"{rel}: name '{name.group(1)}' != directory '{skill_dir.name}'")
        names_seen.setdefault(name.group(1), []).append(str(rel))

    if not re.search(r"^description:", fm, re.M):
        problems.append(f"{rel}: frontmatter missing 'description'")
    if not re.search(r"^license:", fm, re.M):
        problems.append(f"{rel}: frontmatter missing 'license'")

    # Check local references
    local = re.sub(r"`[a-z0-9-]+`\s*skill\s*(?:->|→)\s*`[^`]+`", "", text)
    for ref in sorted(set(re.findall(r"`(references/[^`]+|scripts/[^`]+)`", local))):
        if not (skill_dir / ref).exists():
            problems.append(f"{rel}: dangling reference -> {ref}")

    # Declared config keys
    declared = {k.strip().strip("'\"") for k in re.findall(r"^\s*- key:\s*(\S+)", fm, re.M)}
    for key in sorted(set(CONFIG_KEY_RE.findall(text)) - declared):
        problems.append(f"{rel}: uses config key '{key}' but does not declare it in "
                        f"metadata.hermes.config")

    # Scan all files in skill dir
    for f in sorted(skill_dir.rglob("*")):
        if not f.is_file() or f.suffix not in {".md", ".py", ".sh", ".json", ".yaml", ".yml"}:
            continue
        where = f"{f.relative_to(root)}"
        content = f.read_text(encoding="utf-8", errors="replace")
        for tok in sorted(set(SUBSTITUTION_CLASS.findall(content))):
            problems.append(f"{where}: fill-in token <{tok}> never resolves — declare a "
                            f"metadata.hermes.config key or use ${{HERMES_SKILL_DIR}}")
        for _ln, _line in enumerate(content.splitlines(), 1):
            glued = CORRUPT_VALUE_RE.search(_line)
            if glued:
                problems.append(f"{where}:{_ln}: redaction '{glued.group(0)}' glued to a number/arrow")
        for hit in sorted(set(INSTALL_ROOT_RE.findall(content))):
            problems.append(f"{where}: hardcodes the install root ({hit}) — use ${{HERMES_SKILL_DIR}}")

    for py in skill_dir.rglob("*.py"):
        if subprocess.run([sys.executable, "-m", "py_compile", str(py)], capture_output=True).returncode != 0:
            problems.append(f"{py.relative_to(root)}: py_compile failed")

for name, where in sorted(names_seen.items()):
    if len(where) > 1:
        problems.append(f"duplicate skill name '{name}' in {len(where)} dirs ({', '.join(where)})")

print(f"skills checked: {checked}")

# Check relative markdown links across root docs
doc_problems = []
for pattern in ("*.md", "*/*.md", "Plan/*.md", "Box/*/*.md"):
    for doc in sorted(root.glob(pattern)):
        if not doc.is_file():
            continue
        for raw_target in re.findall(r"\]\((\./[^)#\s]+)\)", doc.read_text(encoding="utf-8")):
            target = urllib.parse.unquote(raw_target)
            if not (doc.parent / target).exists():
                doc_problems.append(f"{doc.relative_to(root)}: broken link -> {target}")

if doc_problems:
    print(f"DOC PROBLEMS ({len(doc_problems)}):")
    for d in doc_problems:
        print("  " + d)
    problems.extend(doc_problems)

if problems:
    print(f"PROBLEMS ({len(problems)}):")
    for p in problems:
        print("  " + p)
    sys.exit(1)

print("OK: skill structure and documentation verified.")
sys.exit(0)
