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

## 4. Install The Overthinkers Skills

The Overthinkers loop connects physiological signals with subjective meaning through 6 core skills declared in `skills/`:
- `detect-baseline`: 28-day rolling baseline ($\mu \pm 1.5\sigma$) slope break detection and athletic strain confounder filter.
- `stress-dialogue`: Cognitive appraisal triage (Distress vs. Eustress vs. Recovery Drain) with $\le 3$ turn ceiling and 1 micro-action commitment.
- `stress-ledger`: Closed-loop outcome ledger, next-day biometric rebound verification, and `MEMORY.md` reflection writeback.
- `samsung-health-import`: Parser and SQLite normalizer for Samsung Health export archives.
- `garmin-import`: Parser and SQLite normalizer for Garmin Connect exports.
- `peer-review`: Multi-agent gut check and quality review runner.

Install the skills into Hermes and restart the gateway:

```bash
mkdir -p ~/.hermes/skills

# Backup any existing skills in Hermes
[ -d ~/.hermes/skills ] && cp -r ~/.hermes/skills ~/.hermes/skills.bak-$(date +%Y%m%d-%H%M%S)

# Copy The Overthinkers skills into Hermes
cp -r ~/overthinkers/skills/* ~/.hermes/skills/

# (Optional) Install companion wearable skills from highlander-longevity-coach (e.g. Apple Health, Oura, Whoop):
if [ ! -d ~/highlander-longevity-coach ]; then
  git clone https://github.com/pridiuksson/highlander-longevity-coach.git ~/highlander-longevity-coach 2>/dev/null || true
fi
if [ -d ~/highlander-longevity-coach/skills ]; then
  cp -r ~/highlander-longevity-coach/skills/* ~/.hermes/skills/ 2>/dev/null || true
fi

# Validate skills structural integrity
python3 ~/overthinkers/scripts/validate-skills.py ~/overthinkers

# Restart the gateway to load new skills
hermes gateway restart
hermes gateway status
hermes skills list
```

---

## 5. Configure Paths, Storage & Quiet Hours

Configure Hermes to know where your biometric data, outcome ledger, and baselines reside:

```bash
hermes config set skills.config.health.health_dir   ~/health
hermes config set skills.config.health.baseline_doc ~/health/baseline.md
hermes config set skills.config.stress.ledger_db    ~/health/data/ledger.db
hermes config set skills.config.proactive.timezone  <TIMEZONE>
hermes config set skills.config.proactive.quiet_hours "08:00-21:00"

mkdir -p ~/health/data ~/.hermes/memories
```

*(Note: Warnings about unrecognized config keys can be safely ignored — Hermes dynamically persists them to `~/.hermes/config.yaml`).*

---

## 6. Instantiate Profiles & Living Context

The Overthinkers uses a 3-tier profile architecture:
- **Tier 1 (`SOUL.md`)**: The AI's mind and operational persona (The Self-Distanced Observer and The Concise Operator).
- **Tier 2 (`USER.md`)**: The human's durable context (wearables, training profile, quiet hours, friction patterns).
- **Tier 3 (`MEMORY.md`)**: The living efficacy ledger under context rent rules (tracking verified intervention recovery correlations).

Bootstrap the profile files into Hermes:

```bash
# 1. Install Tier 1 AI Persona
cp ~/overthinkers/Profile/SOUL.md ~/.hermes/SOUL.md

# 2. Install Tier 2 User Context Scaffold
cp ~/overthinkers/Profile/USER.md ~/.hermes/memories/USER.md

# 3. Install Tier 3 Living Efficacy Ledger
cp ~/overthinkers/Profile/MEMORY.md ~/.hermes/memories/MEMORY.md
```

Edit `~/.hermes/memories/USER.md` with your personal wearable setup, training schedule, and quiet hours.

---

## 7. Interactive Run & Gate Verification

Verify the system end-to-end across the Phase 1 vertical gates:

### Step 7A: Verify Gate 0 (Steel Thread Simulation)
Test the mock trigger and 3rd-person observer check-in:

```bash
python3 ~/overthinkers/scripts/simulate_trigger.py --metric hrv --drop 22
```

Expected output: An outbound check-in using 3rd-person self-distancing framing (*"Biometrics show an autonomic dip today. Looking at your day from the outside, what's taking up your bandwidth?"*), capturing user reply, and closing the session in $\le 2$ turns.

### Step 7B: Verify Gate 1 (Baseline & Confounder Engine)
Verify slope break detection and athletic strain suppression:

```bash
python3 ~/overthinkers/scripts/baseline_math.py check --date $(date +%Y-%m-%d) --db-path ~/health/data/health.db
```

### Step 7C: Verify Gate 3 (Outcome Ledger & Trend Recap)
View the weekly trend recap:

```bash
python3 ~/overthinkers/scripts/orchestrator.py --recap
```

### Step 7D: First Interactive Coaching Session
Launch an interactive Hermes session:

```bash
hermes
```

Run a test dialogue to engage the coach:
> *"Morning. Biometrics show an autonomic dip. Looking at things from the outside, what's taking up your bandwidth?"*

Observe the 80/20 behavioral coaching loop in action:
1. **Self-Distanced Grounding**: The agent inspects the tension as an external strategist.
2. **Cognitive Appraisal Triage**: Categorizes the friction into High Control (Eustress), Low Control (Distress), or Recovery Drain.
3. **Single Micro-Action Commitment**: Suggests exactly 1 bounded tactical micro-action (physiological sigh, 15-minute walk, or task prioritization lock).
4. **Anti-Rumination Circuit Breaker**: Strictly closes the loop within $\le 3$ conversational turns.
5. **Outcome Logging**: Records the intervention into `~/health/data/ledger.db` for next-day biometric rebound verification.

---

## 8. Schedule Proactive Daily Loop (Cron)

To have Hermes automatically evaluate morning baseline slope breaks and proactively initiate a check-in when an authentic anomaly occurs (silence by default):

```bash
hermes cron add \
  --name "overthinkers-morning-check" \
  --schedule "0 8 * * *" \
  --command "python3 $HOME/overthinkers/scripts/orchestrator.py"
```

Verify your active schedules:

```bash
hermes cron list
```
