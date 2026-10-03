# AGENTS — Working Guide for The Overthinkers Repository

This file is the canonical guide for any AI agent working on `TheOverthinkers`. Read it before changing anything.

---

## 1. What This Repository Is

**The Overthinkers** connects wearable biometric anomalies (HRV drops, sleep fragmentation, resting heart rate spikes) to subjective meaning through a structured cognitive dialogue loop on the **Hermes Agent**.

The project follows the **80/20 delivery plan** defined in **[`Plan/PLAN.md`](./Plan/PLAN.md)**:
* **Gate 0:** Steel Thread (Mock trigger → Self-distanced observer chat $\le 2$ turns).
* **Gate 1:** Rolling Baseline & Confounder Engine ($\mu \pm 1.5\sigma$ slope breaks + workout strain filter).
* **Gate 2:** Cognitive Appraisal & Action Triage (Eustress vs. Distress vs. Drain classification + 1 micro-action).
* **Gate 3:** Closed-Loop Outcome Ledger & Personal Model (Next-day biometric verification + outcome ledger).

---

## 2. The Golden Rule: The Leak Gate

Always run the leak gate before proposing or completing any work. **A failing gate means STOP.**

```bash
./scripts/leak-scan.sh .
```

* **No personal measurements:** Never commit raw vitals (e.g. concrete `bpm`, `rmssd`, `kg`). Use `<value>`, `<YOUR_RESTING_HR_BPM>`, or descriptive terms.
* **No credentials or secrets:** Gitleaks scans the tree on every run.
* **No personal identifying handles, emails, or absolute paths.**
* The gate walks the filesystem using `find`, so gitignored files in testing are scanned too.

---

## 3. Skill Layout & Hermes Conventions

Skills live under `skills/<name>/SKILL.md`:

```text
skills/
└── <skill-name>/
    ├── SKILL.md
    ├── scripts/       # (Optional) self-contained helper scripts
    └── references/    # (Optional) markdown reference specs
```

### Frontmatter Contract
Every skill must declare:
```yaml
---
name: <skill-name>
description: "Clear trigger description for Hermes tool routing."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    config:
      - key: <config.key>
        description: "..."
        default: "..."
---
```

1. **Directory name match:** The `name:` in frontmatter must match the directory name exactly.
2. **Self-contained:** A skill owns its own `scripts/` and `references/`. Do not symlink across skill boundaries.
3. **Configuration:** All paths and dynamic settings must be declared under `metadata.hermes.config`. Never hardcode user paths.

Validate structural compliance with:
```bash
python3 scripts/validate-skills.py .
```

---

## 4. Pre-Push Quality Gates

Before finishing a task or opening a pull request, run these validation checks:

```bash
# 1. Leak & secrets check
./scripts/leak-scan.sh .

# 2. Skill structural & doc integrity check
python3 scripts/validate-skills.py .

# 3. Git formatting & whitespace check
git diff --check
```

---

## 5. Working Style & Architectural Bounds

* **80/20 Behavioral Coaching, Not Therapy:** Keep conversations concise ($\le 3$ conversational turns total). Do not engage in open-ended ruminative venting or complex psychiatric roleplaying.
* **Silence by Default:** The coach speaks proactively at most once per day, and only when an anomaly crosses threshold. Normal variance equals silence.
* **Verify, Don't Guess:** Run verification commands against real code and data fixtures rather than assuming they work.
