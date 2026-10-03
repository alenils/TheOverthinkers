---
name: peer-review
description: "Quick gut check from a different LLM via command-code, agy, or mimo. Bounce ideas, catch blind spots, find simpler alternatives. Lighter than @grill. Invoke when you want a second opinion or a quick review of your ideas, plans or delivered work."
allowed-tools:
  - Bash
argument-hint: "<question-or-idea>"
---

# Peer-Review — Quick AI Gut Check

Bounce an idea off a different LLM. Quick sanity check, not deep adversarial analysis.

## Do this

Frame `$ARGUMENTS` as a prompt. The act of writing the prompt forces you to articulate what you're uncertain about — that's where the value is.

The peer runs from the project root and has full file access — reference files by path when helpful.

```bash
.agents/skills/peer-review/scripts/peer-review.sh "<prompt>"
```

Set `cd` to the project root. Set `timeout_ms` to **900000** (15 minutes / 900 seconds). If exit code is **3** (no CLI found), fall back to `spawn_agent` with the same prompt.

### After the peer replies

Report the peer's **main** insight in your own words. If you disagree, explain by bringing in YOUR verified facts based on evidence such as source code.

### When to Use

- Before planning — sanity check an approach
- During implementation — rubber-duck when stuck
- Before committing to a design — second opinion on trade-offs
- Before committing to a technology or architecture choice
