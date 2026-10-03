---
name: commit
description: "Structured conventional commits for The Overthinkers repo. Dual mode: local (autonomous 3-step flow: gather → quality gates → plan & execute) and CI mode (autonomous, 🤖 prefix, PR comment table). Enforces leak-scan, validate-skills, and py_compile before committing."
allowed-tools:
  - Bash
  - Read
  - Grep
  - Glob
argument-hint: "[ci]"
---

# Structured Commits

Create well-scoped, readable commits from current changes in **The Overthinkers**. Groups files by independent intent and applies conventional commit conventions tailored to the 80/20 delivery plan in `Plan/PLAN.md`.

**Dual mode**: local (autonomous 3-step: gather → quality gates → plan & execute) and CI (autonomous, no prompts, `🤖` prefix). CI mode activates when `$ARGUMENTS` contains `ci` **or** env `CI=true`.

---

## Commit Format

Conventional commits with mandatory type and optional gate/component scope:

```text
<type>(<scope>): <imperative description>
```
or
```text
<type>: <imperative description>
```

**Types:**

| Type | Meaning | Example |
|------|---------|---------|
| `feat` | New vertical gate slice or behavioral capability | `feat(gate-0): implement steel thread mock trigger` |
| `fix` | Bug fix, leak patch, schema correction | `fix(skills): resolve frontmatter key in peer-review` |
| `refactor` | Restructuring without changing behavioral contract | `refactor(baseline): streamline rolling slope break math` |
| `test` | Unit tests, mock biometrics, synthetic time series | `test(gate-0): add mock trigger transcript test` |
| `docs` | Plan/*.md, Research/*.md, Box/*.md, README.md | `docs(plan): document Gate 0 bootstrap invariants` |
| `chore` | Config, deps, CI workflows, quality gate scripts | `chore(ci): update leak gate workflow` |
| `style` | Formatting only, whitespace cleanup | `style(scripts): format validate-skills helper` |

**Gate Scopes (from `Plan/PLAN.md`):**
- `gate-0`: Steel Thread & Profile Bootstrap (mock trigger → observer chat)
- `gate-1`: Rolling baseline, confounder engine, wearable imports
- `gate-2`: Cognitive appraisal, action triage, stress dialogue
- `gate-3`: Closed-loop outcome ledger and personal model
- `skills`: Hermes or Claude skill definitions
- `profile`: SOUL, USER, or MEMORY scaffolding
- `box`: Matrix OS cloud box configuration

**Prefix by mode:**

| Mode | Prefix | Example |
|------|--------|---------|
| Local | (none) | `feat(gate-0): add simulate_trigger script` |
| CI | `🤖` | `🤖 fix: update skill frontmatter validation` |

---

## Commit Message Rules

1. **Imperative mood**: "implement mock trigger" not "implemented mock trigger"
2. **Why, not what**: "add timeout fallback (macOS lacks gtimeout by default)" not "update timeout"
3. **No attribution**: Never add co-author, "Generated with Claude", or "Co-Authored-By" lines
4. **Subject under 72 chars**, body wrapped at 72 chars when rationale is needed.
5. **Leak prevention rule**: Never include raw biometric measurements (e.g. concrete heart rate or HRV numbers) or private handles in commit messages! Use descriptive terms like "elevated resting HR" or "HRV anomaly".

---

## Commit Splitting Rules

Split by **independent intent**, not rigidly by file type. Coupled changes stay together:

| Scenario | Split? | Rationale |
|----------|--------|-----------|
| Vertical gate code + its unit test | **No** | Test verifies the gate implementation |
| New skill + its references or docs | **No** | Doc defines the skill contract |
| Gate implementation + unrelated fix to another skill | **Yes** | Independent intents, independent revert risk |
| Profile scaffold + its validator test | **No** | Coupled contract and verification |
| Multiple independent skill adaptations | **Per-skill** | Each skill is independently revertable |
| Only documentation changes across different topics | **By intent** | Group by topic or gate |

**Coupling rule**: If two changes must be reverted together, they must be committed together.

---

## Changed Files Context

!`git status --short 2>/dev/null`
!`git diff HEAD 2>/dev/null; git diff --cached 2>/dev/null`

---

# Local Mode (Default)

Autonomous 3-step flow. Plans and executes without confirmation.

## Step 1: Gather Changes

1. **Review conversation context** — what was done in this session (primary source for intent and why).
2. **Read git status and diff output** — what is actually modified on disk.
3. **Reconcile** — if conversation mentions changes that `git status` doesn't show, verify save status before proceeding.

If no changes found → report "Nothing to commit" and stop.

## Step 2: Quality Gates (Quick Checks)

Before committing, run the repository's mandatory pre-push quality gates.

### 1. Blocking: Whitespace & Conflict Markers

```bash
git diff --check
```

**On failure**: report the errors and **stop**. Fix whitespace issues or conflict markers before proceeding.

### 2. Blocking: The Golden Rule (Leak Gate)

```bash
./scripts/leak-scan.sh .
```

**On failure**: **STOP IMMEDIATELY**.
- Inspect flagged hits for personal vitals (concrete heart rate, RMSSD, weight), tokens, credentials, or private paths.
- Redact values to `<value>`, `<YOUR_RESTING_HR_BPM>`, or descriptive terms.
- Do not bypass this check under any circumstance.

### 3. Blocking: Skill Structural & Markdown Integrity

```bash
python3 scripts/validate-skills.py .
```

**On failure**: report the validation errors and **stop**. Verify YAML frontmatter, parent directory naming, declared config keys, and relative markdown links.

### 4. Blocking: Python Syntax Validation

```bash
{ git diff --name-only HEAD -- '*.py'; git ls-files --others --exclude-standard -- '*.py'; } | sort -u | xargs -r python3 -m py_compile
```

**On failure**: report the failing file and line, **stop**. Fix Python syntax errors before committing.

### 5. Blocking: Pre-staged Files Check

```bash
git diff --cached --name-only
```

If this returns files **not touched in this session's conversation context**, another agent or process pre-staged them. List the unexpected files and **stop**:
> "⚠️ These files were pre-staged by another process: `<file list>`. Run `git reset HEAD <files>` or commit them manually before proceeding."

### Advisory Flags (Non-blocking)

Display these after the commit plan in Step 3. These never block a commit:

| If changed files include... | Advisory Note |
|---|---|
| `skills/*/SKILL.md` or `.claude/skills/*/SKILL.md` | Recommend running `peer-review` on the skill changes |
| `Plan/PLAN.md` or `Research/*.md` | Verify gate DoD alignment against the 80/20 delivery plan |
| `Profile/*.md` | Confirm the rent rule is respected and no raw personal vitals entered `MEMORY.md` |
| `Box/` | Verify configuration matches Matrix box cookbook specifications |

**Cross-thread isolation**: Multiple agents or sessions may work simultaneously. Only stage files touched in this session. If `git status` shows modified (`M`) or untracked (`??`) files you did not touch, leave them unstaged and warn:
> "⚠️ `<file>` is modified/untracked but was not touched in this session — leaving unstaged."

## Step 3: Plan & Execute

Group files by independent intent using the splitting rules. Plan the commits, then execute immediately without confirmation.

For each group, determine:
- **Type and scope** from conventional commit conventions
- **Message** following imperative message rules
- **Files** to stage for this specific commit

Present the plan:

```text
### Commit Plan (N commits)

**1.** `type(scope): message`
   - `path/to/file1`
   - `path/to/file2`

**2.** `type(scope): message`
   - `path/to/file3`
```

### Execute

1. For each planned commit: `git add <file1> <file2>` (stage specific files only; never `git add -A` or `git add .`).
2. Commit: `git commit -m "<message>"`.
3. Display `git log --oneline -n N` to confirm.
4. Display advisory flags from Step 2 if any apply.

---

# CI Mode

Activated when `$ARGUMENTS` contains `ci` **or** env `CI=true`. Autonomous — no interactive prompts, no confirmation.

## CI Git Context

The workflow runs `git reset --soft origin/main` — all changes are staged. **`git diff --cached` is the canonical diff source.**

## CI Step 1: Gather Changes

1. **Read `git diff --cached`** — the source of truth in CI.
2. **Run quick checks**:
   - `git diff --check --cached`
   - `./scripts/leak-scan.sh .`
   - `python3 scripts/validate-skills.py .`
   - `git diff --cached --name-only -- '*.py' | xargs -r python3 -m py_compile`
3. If checks fail or nothing staged → report error and stop.

## CI Step 2: Plan Commits

Apply splitting rules and prefix all messages with `🤖 `:
- `🤖 feat(gate-0): ...`
- `🤖 fix(skills): ...`

When splitting intent is ambiguous from the diff alone, commit together as a coherent vertical slice.

## CI Step 3: Execute

1. For each planned commit:
   - `git reset HEAD` to start clean
   - `git add <specific files>`
   - `git commit -m "🤖 <type>(<scope>): <message>"`
2. Never use `git add -A` or `git add .`.

## Structured Output

End with a summary suitable for PR comments:

```markdown
## Commits Created

| # | Message | Files |
|---|---------|-------|
| 1 | 🤖 feat(gate-0): implement mock trigger | scripts/simulate_trigger.py |
| 2 | 🤖 test(gate-0): add trigger execution tests | tests/test_gate0_bootstrap.py |

**Total**: N commit(s), M file(s)
```
