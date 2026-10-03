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

## 3. Configure Model & Audio Credentials

Configure your preferred LLM and TTS provider:

### Google Gemini (Recommended for fast reasoning & native audio)
```bash
# Set your Google API key in ~/.hermes/.env:
echo "GOOGLE_API_KEY=<YOUR_KEY>" >> ~/.hermes/.env

# Configure inference model to Gemini 3.8 Flash
hermes config set model.provider gemini
hermes config set model.default gemini-3.8-flash

# (Optional) Enable native Gemini TTS audio for voice notes & audio output
hermes config set tts.provider gemini
hermes config set tts.gemini.model gemini-3.8-flash-tts
hermes config set tts.gemini.voice Kore
```

### Alternative: OpenRouter or Anthropic
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

## 5. Install Profiles and Use One Runtime Home

The installer, importer CLIs, orchestrator, and ledger share `HERMES_HOME`, falling back to `~/.hermes`. Repository `Profile/` files are generic templates. Runtime readings and populated memories stay outside the checkout.

```bash
python3 ~/overthinkers/scripts/install_runtime.py --dry-run
python3 ~/overthinkers/scripts/install_runtime.py
hermes skills list
```

The installer places `SOUL.md` at the runtime root, and `USER.md` plus `MEMORY.md` under `memories/`, matching Hermes 0.21.4. It preserves existing personalized files, migrates an older runtime `Profile/` scaffold if present, and backs up installed skills before replacing them. Review `SOUL.md` if an existing persona was preserved. Skill discovery and a human inspection of the loaded persona remain deployment acceptance checks.

Defaults are `data/health.db`, `data/garmin.db`, `data/ledger.db`, and `state/` inside that home. Set Hermes skill configuration paths to the same runtime data paths when using the skills directly. For a custom home, export `HERMES_HOME` for the installer, Hermes, imports, daily process, and reply worker; explicit command-line paths override these defaults.

```bash
export STRESS_TIMEZONE="<IANA_TIMEZONE>"
export STRESS_ALLOWED_HOURS="08:00-21:00"
```

The Python runner reads these environment settings, not the Hermes `proactive` config keys. UTC is the fallback timezone. On Windows, a non-UTC IANA timezone requires the Python `tzdata` package.

## 6. Test Explicit Mock Mode & Gate Verification

Verify the system end-to-end across the Phase 1 vertical gates:

### Step 6A: Verify Gate 0 (Steel Thread Simulation)
Test the mock trigger and 3rd-person observer check-in:

```bash
python3 ~/overthinkers/scripts/simulate_trigger.py --metric hrv --deviation -2.2 --interactive
```

Expected output: An outbound check-in using 3rd-person self-distancing framing (*"Biometrics show an autonomic dip today. Looking at your day from the outside, what's taking up your bandwidth?"*), capturing user reply, and closing the session in $\le 2$ turns.

### Step 6B: Verify Gate 1 (Baseline & Confounder Engine)
Verify slope break detection and athletic strain suppression:

```bash
python3 ~/overthinkers/scripts/baseline_math.py check --date $(date +%Y-%m-%d) --db-path ~/health/data/health.db
```

### Step 6C: Verify Gate 3 (Outcome Ledger & Trend Recap)
View the weekly trend recap:

```bash
python3 ~/overthinkers/scripts/simulate_trigger.py --interactive --ignore-quiet-hours
python3 ~/overthinkers/scripts/orchestrator.py --interactive
python3 ~/overthinkers/scripts/orchestrator.py --recap
```

Gate 0 uses repository profile templates to exercise a two-message mock dialogue; it does not prove Hermes loaded its runtime persona. Simulated alerts are labeled. Without an explicit mock reply or interactive input, sessions remain pending; EOF never creates invented user context. Gate 2 caps coach messages at three, including clarification and the proposal. Action acceptance requires a later reply; acceptance and reported completion are separate fields.

The current runner uses deterministic appraisal rules. A separate `hermes` chat uses its configured model and persona; it does not automatically log that chat to this runner's ledger.

## 7. Configure Telegram Delivery and Replies

Create a Telegram bot and start a **private** conversation with it. Keep the bot token, intended chat ID, and intended user ID in a private environment file or secret manager outside the checkout. Export these variables to both the daily runner and reply worker:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `TELEGRAM_USER_ID`

No credentials are needed for repository tests. The transport uses Telegram's [sendMessage and getUpdates API](https://core.telegram.org/bots/api). Polling requires no active webhook and **one poller per bot**. Replies must come from the configured user in the configured private chat, using Telegram's Reply function on the latest coach message; unrelated messages do not enter the session.

```bash
python3 ~/overthinkers/scripts/orchestrator.py --channel telegram
python3 ~/overthinkers/scripts/orchestrator.py --poll
# Or keep a supervised worker running to poll replies and expire unanswered sessions:
python3 ~/overthinkers/scripts/orchestrator.py --watch
```

The daily command requires imported wearable data and enough same-source history. Unknown workout context suppresses proactive outreach. It sends at most one opening per local day, reserves that limit before HTTP, and journals every outbound attempt. A failed/interrupted send stays `DELIVERY_UNCERTAIN` and is never automatically retried. Inspect private `state/messaging/` records before taking manual recovery action. Missing replies expire silently after one hour; run the worker to apply expiration. A restart replays durable replies without duplicate coach messages or ledger entries.

The closing proposal may ask for confirmation within the existing message budget. A later confirmation updates acceptance/completion without another coach message. Vague statements, silence, and unrelated replies cannot establish completion.

## 8. Configure WhatsApp & Gemini 3.8 Voice Gateway (Optional)

Test an end-to-end simulated check-in dispatched directly to your phone via WhatsApp:

```bash
python3 ~/overthinkers/scripts/e2e_whatsapp_demo.py --recipient <YOUR_PHONE_NUMBER>
```

Hermes sends the morning check-in to your WhatsApp chat. Reply with text or an audio voice note:
- Voice notes are transcribed in ~0.4s using `gemini-3.8-flash` via `google-genai`.
- Hermes runs the Gate 2 cognitive appraisal triage and replies back with 1 actionable micro-step.
- The check-in is logged to `data/ledger.db` on your Matrix box.

## 9. Inspect Matrix OS Desktop Control Center (GUI)

If running on Matrix OS, click the **Hermes Agent** app icon on your Matrix desktop:
- **Live System Telemetry**: Monitors Gemini 3.8 Flash, gateway status, and quiet hours.
- **How It Works**: Interactive visual explainer of the 80/20 delivery gates and `Diagram.md` appraisal matrix.
- **Interactive Simulator**: Step-by-step interactive simulator walking through real-time check-in and confounder evaluation.
- **Outcome Ledger Feed**: Live table reflecting recovery rebounds from `~/health/data/ledger.db`.

Run a test dialogue to engage the coach:
> *"Morning. Biometrics show an autonomic dip. Looking at things from the outside, what's taking up your bandwidth?"*

## 10. Daily Operation and Follow-Up Checks

Schedule the daily command with `--channel telegram` in your chosen scheduler, ensuring it and the reply worker receive the same runtime home, timezone, and Telegram environment. Keep the reply worker supervised. The deterministic runner does not require Hermes model credentials.

Verification matches the next night's source and metric to the frozen trigger baseline. Missing follow-ups expire after 48 hours. Zero-variance baselines remain unverifiable. Old ledger schemas migrate additively; old records lacking provenance stay excluded from action summaries.

Memory retains proposal counts, uncertainty, and excluded observations. Action summaries require at least five reported completed actions with real, matched follow-ups and verified context, grouped by source and metric. Biometric recovery is an observation, never proof the action caused it. Provider-specific units are kept separate; the current database has no within-provider device or measurement-version identifier, so use separate runtime data when changing those definitions.

```bash
python3 -B -m unittest discover -s tests -v
python3 scripts/validate-skills.py .
./scripts/leak-scan.sh .
git diff --check
```

A live Telegram smoke test and Hermes profile discovery must still be checked on your configured cloud runtime.
