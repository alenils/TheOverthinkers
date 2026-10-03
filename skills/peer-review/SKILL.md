---
name: peer-review
description: "Use BEFORE acting on any unverified assumption or guess. Quick second opinion from a different LLM via CLI (command-code, agy, mimo). Catches blind spots, prevents confident errors."
version: 2.3.0
author: ported from oracle
license: MIT
metadata:
  hermes:
    tags: [review, second-opinion, peer, sanity-check, command-code, agy, mimo]
---

# Peer-Review — Quick AI Gut Check

Bounce an idea off a different LLM. Quick sanity check, not deep adversarial analysis.

## Do this

**Before framing the prompt: fact-check what you can verify yourself.** The most effective peer reviews are narrowly scoped to genuine judgment calls, not things you could check with a terminal or file read. Audit the document/decision against source code, config files, or actual CLI output FIRST. Resolve every verifiable claim on your own. Then frame the peer prompt around ONLY what remains genuinely uncertain — design trade-offs, human-factors judgments, or questions where no source-of-truth exists.

Frame the request as a prompt:

```bash
${HERMES_SKILL_DIR}/scripts/peer-review.sh "your prompt here"
```

Use the **terminal** tool to run the script. Set a **5-minute timeout** (300 seconds).

### Fallback chain

| Exit code | Meaning | Action |
|-----------|---------|--------|
| 0 | Success — a CLI returned a response | Read stdout, proceed to evaluation |
| 1 | No prompt provided OR script error | Usage error: fix and retry |
| 3 | **No peer CLI available** — none installed, or all installed ones failed | **Use the native subagent fallback** |

The chain attempts `command-code → agy → mimo → exit 3`.

### Subagent fallback (Exit 3)

If the script exits **3** (e.g., in an environment without peer CLIs): spawn a subagent as the peer:

```text
Goal: You are a peer reviewer. Give a quick, honest second opinion on this question. Do not rubber-stamp — flag blind spots and simpler alternatives. Keep it under 200 words.
```

### After the peer replies

1. Report the peer's **main** insight in your own words.
2. Critically evaluate — don't rubber-stamp.
3. If the peer agrees too easily, probe with: *"What is one specific way this could fail in production?"*
4. Push back when peer claims contradict verified source evidence.

### When to Use

- Before planning — sanity check an approach
- During implementation — rubber-duck when stuck
- Before committing to a design — second opinion on trade-offs
- Before committing to an architecture or technology choice
