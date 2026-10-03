# Onboarding — Setting Up The Overthinkers on Hermes

This guide walks you from a clean computer to a running Hermes Agent box executing the Overthinkers stress dialogue loop.

---

## 0. Prerequisites

| Need | Why |
|---|---|
| **A machine to run on** | Needs 24/7 uptime for gateway and cron. Follow the [Matrix OS Cookbook](./Box/Matrix/matrix-box-cookbook.md) to stand up a cloud box in ~10 minutes. |
| **Hermes Agent** (v0.21.0+) | The runtime environment hosting the skills, gateway, and loops. Verify with `hermes --version`. |
| **Python ≥ 3.11** | For analysis and data transformation scripts. |
| **Git** | To clone and manage repositories. |
| **Model API Key** | OpenRouter, Anthropic, OpenAI, or Nous key to power the agent reasoning. |

---

## 1. Clone the Repository

On your machine or remote Matrix instance:

```bash
git clone https://github.com/alenils/TheOverthinkers.git ~/overthinkers
cd ~/overthinkers
git rev-parse HEAD    # Record this commit hash for reproducibility
```

---

## 2. Verify Hermes & Gateway Service

Ensure Hermes is installed and the background gateway service is active:

```bash
hermes --version
hermes gateway install
hermes gateway restart
hermes gateway status
```

Status should be `active (running)`.

---

## 3. Configure Model Credentials

Configure your preferred LLM provider:

```bash
# Interactive selection
hermes model

# Or set via environment in ~/.hermes/.env:
echo "OPENROUTER_API_KEY=<YOUR_KEY>" >> ~/.hermes/.env
```

Verify agent connectivity with a quick test:

```bash
hermes -z "Reply with the single word: alive"
```

---

## 4. Install Companion Wearable Skills (Optional)

The Overthinkers loop connects physiological signals with subjective meaning. To ingest Garmin, Samsung Health, or Apple Health data, you can install companion skills from the `highlander-longevity-coach` repository:

```bash
if [ ! -d ~/highlander-longevity-coach ]; then
  git clone https://github.com/pridiuksson/highlander-longevity-coach.git ~/highlander-longevity-coach
fi

mkdir -p ~/.hermes/skills
cp -r ~/highlander-longevity-coach/skills/* ~/.hermes/skills/ 2>/dev/null || true

hermes gateway restart
hermes skills list
```

---

## 5. Configure Paths & Quiet Hours

Configure Hermes to know where your biometric data and baselines reside:

```bash
hermes config set skills.config.health.health_dir   ~/health
hermes config set skills.config.health.baseline_doc ~/health/baseline.md
hermes config set skills.config.proactive.timezone  <TIMEZONE>
hermes config set skills.config.proactive.quiet_hours "08:00-21:00"

mkdir -p ~/health
```

*(Note: Warnings about unrecognized config keys can be safely ignored — Hermes persists them to `~/.hermes/config.yaml`).*

---

## 6. Personal Context & Baseline

Create your baseline file in `~/health/baseline.md` and define your personal parameters:

- Known stress triggers (work context, sleep deficit, conflict styles)
- Baseline resting HR and HRV ranges
- Preferred communication tone (e.g. direct, grounding, compassionate)

---

## 7. First Interactive Run

Launch an interactive Hermes session:

```bash
hermes
```

Run a test scenario to trigger the loop:
> *"My wearable showed an HRV dip this morning and my resting HR is elevated. Let's do the stress dialogue loop."*

Observe the agent transition through the stages:
1. **Detect**: Clarifying biometric anomaly vs workout or physiological confounders.
2. **Ground**: Enforcing self-distanced 3rd-person framing.
3. **Dialogue**: Initiating the two-chair dialogue.
4. **Map**: Identifying active coping modes and underlying emotions.
5. **Rescript**: Introducing the healthy adult intervention.
6. **Track**: Logging resolution and emotional shift.
