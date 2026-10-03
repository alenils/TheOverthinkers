---
name: create-pr
description: "Lift commits onto a named branch and open a PR — without checkout. Runs diff check, leak scan, and skill validation before pushing, and formats PR with Gate DoD alignment. Safe when another agent works on the same branch. Designed as the step after /commit."
allowed-tools:
  - Bash
  - Read
  - Glob
argument-hint: "[branch-name]"
---

# Create PR

Takes commits that landed on the current branch (often `main`) and opens a pull request — **without ever running `git checkout`**. Runs the repository's pre-push quality gates (whitespace check, leak scan, and skill validator) before pushing so the branch is clean when it lands on origin.

The full flow:

```text
/commit        → commits land on current branch
/create-pr     → pre-push quality gates → branch (no checkout) → push → gh pr create
```

## Diff & Quality Gate Checks

Before pushing, run the four mandatory repository gates:

```bash
git diff --check origin/main..HEAD
./scripts/leak-scan.sh .
python3 scripts/validate-skills.py .
python3 -m unittest discover tests
```

- **Diff check**: Catches whitespace errors, conflict markers, and blank lines at end of files.
- **Leak gate**: Verifies zero personal vitals, zero secrets, zero private handles or paths.
- **Skill validation**: Confirms YAML frontmatter, directory naming, and documentation integrity.
- **Automated test suite**: Runs all 30 tests verifying Gates 0 through 3 end-to-end.

**Advisory — peer review for skill changes**: if any changed file is under `skills/` or `.agents/skills/`, note it in the PR body. Skill definitions are self-contained and high-leverage — run `/peer-review` or recommend review before merge.

---

## Core Invariant

**Never run `git checkout`, `git switch`, or `git checkout -b`.**

Branch creation (`git branch <branch-name> <HEAD_SHA>`) writes a git ref without moving `HEAD`. Editors, watchers, and parallel agent sessions watch `HEAD` — since it never moves, they remain completely undisturbed. This skill creates and pushes branches exclusively via ref writes and `git push`.

---

## Step 1: Identify Commits to PR

```bash
git fetch origin main
git log origin/main..HEAD --oneline
git rev-parse HEAD
```

Fetch first — ensures `origin/main` is current before diff checks. Without this, recently merged PRs on main will inflate the diff scope.

- If `git log` is empty → report "Nothing ahead of origin/main — nothing to PR" and stop.
- Capture `HEAD_SHA` for branch creation.

---

## Step 2: Run Pre-Push Quality Gates

Run all four gates:

1. **Whitespace & conflict markers**:
   ```bash
   git diff --check origin/main..HEAD
   ```
2. **The Leak Gate**:
   ```bash
   ./scripts/leak-scan.sh .
   ```
3. **Skill & doc integrity**:
   ```bash
   python3 scripts/validate-skills.py .
   ```
4. **Automated test suite (Gates 0–3)**:
   ```bash
   python3 -m unittest discover tests
   ```

**On any failure**: stop immediately and report the error. Do not create or push a branch until all gates pass cleanly.

---

## Step 3: Determine Branch Name

If `$ARGUMENTS` contains a branch name → use it as-is.

Otherwise derive from the **first commit message** in the range (oldest first):

```bash
git log origin/main..HEAD --oneline --reverse | head -1
```

Derivation rules:
1. Strip conventional commit type/scope prefix: `feat(gate-0): ` → drop `feat(gate-0): `
2. Lowercase, replace spaces/slashes/parens with `-`
3. Remove special chars except `-` and `_`
4. Truncate to 50 chars
5. Prefix with type slug: `feat/`, `fix/`, `docs/`, `chore/`, `refactor/`

Examples:
- `feat(gate-0): implement mock trigger` → `feat/gate-0-implement-mock-trigger`
- `fix(skills): resolve frontmatter issue` → `fix/skills-resolve-frontmatter-issue`
- `docs(plan): update gate 1 requirements` → `docs/plan-update-gate-1-requirements`

Check for collision on origin:
```bash
git ls-remote --exit-code origin <branch-name>
```
If branch already exists on origin, append `-2`, `-3` until free.

---

## Step 4: Create Branch and Push (No Checkout)

```bash
git branch <branch-name> <HEAD_SHA>
git push -u origin <branch-name>
```

**Never run `git checkout`** — HEAD stays where it is.

If `git branch` fails because a local branch with that name already exists: `git branch -f <branch-name> <HEAD_SHA>`.

---

## Step 5: Draft PR Title and Body

**Title**: First commit message if single commit; synthesize from the range otherwise. Max 70 chars.

### Advisory Flags

Run: `git diff origin/main..HEAD --name-only` and evaluate:
- **Skill changes**: any file under `skills/` or `.agents/skills/` → `SKILLS_CHANGED = true`
- **Plan / Research changes**: any file under `Plan/` or `Research/` → `PLAN_CHANGED = true`
- **Profile changes**: any file under `Profile/` → `PROFILE_CHANGED = true`
- **Box changes**: any file under `Box/` → `BOX_CHANGED = true`
- **Security changes**: any file touching `.gitleaks.toml`, `.leakignore`, or `scripts/leak-*` → `SECURITY_CHANGED = true`

Determine which vertical gate is advanced (`Gate 0`, `Gate 1`, `Gate 2`, `Gate 3`, or `Foundations/Chore`).

### Body Template

**Copy this template and populate the sections. Do not omit sections.**

```markdown
## Summary

<2–4 bullet points covering what changed, why, and which Gate in Plan/PLAN.md this PR advances>

## Vertical Gate DoD Alignment

<Check off relevant items according to the targeted gate in Plan/PLAN.md:>
- [ ] Gate DoD criteria verified against real code and fixtures
- [ ] Conversational boundaries preserved (<= 3 turns, silence by default)
- [ ] Anti-rumination circuit breaker validated

## Changed Files

<details><summary>Files changed in this PR</summary>

<For each changed file, add one line summarizing key modifications:>

- `.agents/skills/commit/SKILL.md` — structured conventional commits with leak-scan integration
- `scripts/simulate_trigger.py` — mock biometric trigger generator for Gate 0

</details>

## Quality Gates Passed

- **Diff check**: ✅ `git diff --check origin/main..HEAD` passed (no whitespace or conflict markers)
- **Leak gate**: ✅ `./scripts/leak-scan.sh .` passed (zero personal vitals, zero secrets)
- **Skill integrity**: ✅ `python3 scripts/validate-skills.py .` passed
- **Unit tests**: ✅ `python3 -m unittest discover tests` passed (30/30 tests)
- **Peer review**: ⏭ not flagged / ⚠️ skill files changed — peer review recommended

## Test Plan

- [x] Local unit tests passed (`python3 -m unittest discover tests`)
- [x] Pre-push quality gates verified clean
- [ ] CI workflow verification

## Review Context

> Context for reviewers mapping the diff back to intent.

**Intentional changes that may look suspicious:**
<List any diff hunks that alter thresholds, conditions, or defaults, with rationale. If none, state: None — straightforward addition.>

**Confirmed by testing:**
<Commands and outputs verified prior to PR, e.g. "Ran test_gate0_bootstrap.py; all 4 tests passed.">

**Not touched (deliberately deferred):**
<Areas intentionally deferred per the 80/20 delivery plan in Plan/PLAN.md.>
```

---

## Step 5.5: Verify Body Completeness

Before opening the PR, confirm all required sections are present:
- [ ] `## Summary`
- [ ] `## Vertical Gate DoD Alignment`
- [ ] `## Changed Files`
- [ ] `## Quality Gates Passed`
- [ ] `## Test Plan`
- [ ] `## Review Context`

---

## Step 6: Open PR

```bash
gh pr create \
  --title "<title>" \
  --body "<body>" \
  --base main \
  --head <branch-name>
```

---

## Step 7: Report

```text
## PR Created

**Branch**: `<branch-name>` (created at <short-sha>, HEAD stayed on `<current-branch>`)
**PR**: <url>
**Commits**: <N>
**Checks**: ✅ diff check passed / ✅ leak scan passed / ✅ skill validation passed

| # | Commit |
|---|--------|
| 1 | <sha> <message> |

**Local state**: HEAD still on `<current-branch>` — no checkout performed.
```

---

## Already on a Feature Branch

If `git branch --show-current` returns something other than `main`:
- Skip branch creation
- Run `git push -u origin <current-branch>`
- Proceed to draft PR title/body and execute `gh pr create`

---

## Error Handling

| Condition | Action |
|-----------|--------|
| Nothing ahead of `origin/main` | Report and stop — nothing to PR |
| Quality gate fails (leak scan, diff check, skill validation) | Stop — fix flagged errors; do not push |
| Branch name collision on origin | Append `-2`, `-3` until free |
| `git push` fails (non-fast-forward) | Report error — do not force push |
| `gh pr create` fails | Report error; branch is pushed, user can create PR via CLI or web UI |
```