# Box — Matrix: a Cloud Hermes Agent Box via Matrix OS

**Point your agent at this file.** The agent standing in front of you — Zed agent, Claude Code,
Hermes, Command Code, or any agent that can run shell commands — executes this cookbook top to bottom.
When it needs something only a human has (a login, an API key, a personal decision), it stops at a
**⛔ stop-point** and asks. You do two brief steps by hand; the agent does the rest.

What you get: a cloud-hosted Matrix OS computer running the Hermes agent, with the Overthinkers
stress dialogue loops and companion skills installed, a persistent background gateway, and a
dedicated Hermes desktop application pinned to the Matrix OS web desktop.

What it costs: a Matrix OS account with an active Matrix computer instance. Matrix manages the
compute lifecycle, container runtime, code server, and terminal multiplexing.

---

## Before you start (human)

| Need | Why |
|---|---|
| A Matrix OS account at `matrix-os.com` | provides the cloud computer and gateway |
| A web browser | authentication happens at A3 via OAuth device flow |
| Node.js ≥ 20 on your local machine | required to run the Matrix CLI (`@finnaai/matrix`) |
| A terminal with an agent in it | the executor running this cookbook |
| ~10–15 minutes | mostly automated agent-driven provisioning |

---

## Variables — set these once, at the top

The run needs these values. Confirm them before Phase B:

| Variable | Default | Notes |
|---|---|---|
| `<TIMEZONE>` | `UTC` | IANA name (`Europe/Stockholm`, `America/New_York`, etc.), used at B6 |
| `<MATRIX_PROFILE>` | `cloud` | CLI profile name (default is `cloud`) |
| `<HEALTH_DIR>` | `~/health` | Path for biometric and personal data on the Matrix computer |
| `<REPO_URL>` | `https://github.com/alenils/TheOverthinkers.git` | This repository |

**Rule for the executing agent:** confirm `<TIMEZONE>` with the human before Phase B.

---

## Phase A — on your local machine

### A1 — preflight

```bash
node -v && npm -v && curl --version
```

Node must be ≥ 20. Both macOS and Linux are supported local hosts.

### A2 — install the Matrix CLI

The official package is `@finnaai/matrix`. On Linux hosts, install in an isolated prefix to
avoid optional macOS build dependencies (`fsevents` gyp rebuild failure):

```bash
mkdir -p ~/.local/share/finnaai-matrix
npm install --prefix ~/.local/share/finnaai-matrix @finnaai/matrix

# Link binaries into ~/.local/bin (must be in your PATH)
mkdir -p ~/.local/bin
ln -sf ~/.local/share/finnaai-matrix/node_modules/.bin/matrix ~/.local/bin/matrix
ln -sf ~/.local/share/finnaai-matrix/node_modules/.bin/matrixos ~/.local/bin/matrixos
ln -sf ~/.local/share/finnaai-matrix/node_modules/.bin/mos ~/.local/bin/mos

matrix --version
```

Expect version `0.3.21` or newer.

> **Gotcha noted:** The standalone curl installer (`curl -fsSL https://get.matrix-os.com | sh`)
> may 404 upstream. Installing via `npm` into an isolated prefix is the reliable path.

### A3 — ⛔ authenticate (human: browser)

```bash
matrix login
```

The CLI prints a one-time device code and authorization link:
```text
Visit: https://app.matrix-os.com/auth/device?user_code=XXXX-XXXX
Enter code: XXXX-XXXX
```

Open the link in your browser, log in to Matrix OS, and approve the device. The CLI will
automatically detect authorization and save your profile credentials to `~/.matrixos/`.

Verify before proceeding:

```bash
matrix whoami        # must show your handle and (cloud)
matrix status        # must report Gateway: ok, Authenticated: yes
```

### A4 — instance check

Verify that your Matrix computer is active:

```bash
matrix instance info
```

Expect a JSON response showing your instance running, CPU count, memory, and status `available`.

---

## Phase B — on the Matrix computer

Commands on the Matrix computer are driven through the Matrix CLI via:
`matrix run --project=main -C . -- <COMMAND>`

> **Agent notes on `matrix run`:**
> 1. **Always pass `--project=main -C .`**: In `@finnaai/matrix` v0.3.21, running `matrix run`
>    without a project or with an empty CWD triggers an HTTP 400 schema error on the gateway.
>    `--project=main -C .` resolves to the workspace root cleanly.
> 2. **Avoid local tilde expansion**: The local shell expands `~` to `<LOCAL_HOME>`, but
>    on the Matrix computer you want the remote user's `$HOME`. Quote remote commands or use
>    `bash -lc '...'` so tilde/variable expansion happens on the Matrix machine.
> 3. **Avoid monolithic long commands**: The Matrix gateway reverse-proxy times out on single
>    HTTP calls exceeding ~30–60 seconds (HTTP 504). Keep operations modular and targeted.

### B1 — base packages + tools

The Matrix computer runs Ubuntu 24.04 LTS. Python, Node.js, and git are pre-installed. Install `jq`
and `gitleaks` (useful for leak protection and secrets validation):

```bash
# Install jq
matrix run --project=main -C . -- sudo DEBIAN_FRONTEND=noninteractive apt-get update -qq
matrix run --project=main -C . -- sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq jq

# Install gitleaks (pinned v8.30.1)
matrix run --project=main -C . -- curl -fsSL -o /tmp/gitleaks.tar.gz \
  https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_linux_x64.tar.gz
matrix run --project=main -C . -- tar -xzf /tmp/gitleaks.tar.gz -C /tmp
matrix run --project=main -C . -- sudo install /tmp/gitleaks /usr/local/bin/gitleaks
matrix run --project=main -C . -- gitleaks version
```

`gitleaks version` should report `8.30.1`.

### B2 — Hermes agent & gateway setup

Hermes is pre-provisioned on the Matrix computer under `~/.hermes` with the binary
at `~/.local/bin/hermes`.

Verify the installation and enable the persistent gateway service:

```bash
matrix run --project=main -C . -- bash -lc 'hermes --version'
```

Install and start the gateway systemd service:

```bash
matrix run --project=main -C . -- bash -lc 'hermes gateway install'
matrix run --project=main -C . -- bash -lc 'hermes gateway status'
```

Expect `active (running)`. Systemd linger is enabled by default so the gateway survives session
disconnects.

### B3 — ⛔ model credentials (human: interactive)

The agent cannot provide private API keys or interact with OAuth prompts on your behalf.

Run `matrix shell new --name auth` or launch a terminal tab from the Matrix OS web interface, then:

```bash
hermes model
```

Pick your preferred model provider (e.g. Google Gemini, Nous, OpenRouter, Anthropic, or OpenAI).

For **Google Gemini** (including native TTS audio):
```bash
# 1. Add your Google API key to ~/.hermes/.env
matrix run --project=main -C . -- bash -lc 'echo "GOOGLE_API_KEY=<KEY>" >> ~/.hermes/.env'

# 2. Configure model inference to Gemini 3.8 Flash
matrix run --project=main -C . -- bash -lc '
hermes config set model.provider gemini
hermes config set model.default gemini-3.8-flash
'

# 3. (Optional) Configure Gemini TTS for voice audio (Telegram/WhatsApp notes & TTS tool)
matrix run --project=main -C . -- bash -lc '
hermes config set tts.provider gemini
hermes config set tts.gemini.model gemini-3.8-flash-tts
hermes config set tts.gemini.voice Kore
'
```

Alternatively, for OpenRouter or Anthropic:
```bash
matrix run --project=main -C . -- bash -lc 'echo "OPENROUTER_API_KEY=<KEY>" >> ~/.hermes/.env'
```

Verify with a quick round-trip before proceeding:

```bash
matrix run --project=main -C . -- bash -lc 'hermes -z "Reply with the single word: alive"'
```

### B4 — clone The Overthinkers repository

Clone this repository into the Matrix home directory:

```bash
matrix run --project=main -C . -- \
  bash -lc 'git clone https://github.com/alenils/TheOverthinkers.git ~/overthinkers'

matrix run --project=main -C overthinkers -- git rev-parse HEAD
```

Write down the commit SHA — this records the exact version running on your Matrix box.

### B5 — install The Overthinkers skills & run quality gates

The Overthinkers repository ships with 6 core skills under `skills/`:
- `detect-baseline`: 28-day rolling baseline ($\mu \pm 1.5\sigma$) slope break detection and athletic strain confounder filter.
- `stress-dialogue`: Cognitive appraisal triage (Distress vs. Eustress vs. Recovery Drain) with $\le 3$ turn ceiling.
- `stress-ledger`: Closed-loop outcome ledger, next-day biometric rebound verification, and `MEMORY.md` writeback.
- `samsung-health-import`: Parser and SQLite normalizer for Samsung Health export archives.
- `garmin-import`: Parser and SQLite normalizer for Garmin Connect exports.
- `peer-review`: Multi-agent gut check and quality review runner.

1. **Backup existing skills and check collisions**:
   ```bash
   matrix run --project=main -C . -- bash -c '
   backup_dir="$HOME/.hermes/skills.bak-$(date +%Y%m%d-%H%M%S)"
   [ -d "$HOME/.hermes/skills" ] && cp -r "$HOME/.hermes/skills" "$backup_dir"
   existing=$(find -L "$HOME/.hermes/skills" -name SKILL.md -not -path "*/.archive/*" -exec grep -h "^name:" {} + 2>/dev/null | awk "{print \$2}" | sort -u)
   incoming=$(find "$HOME/overthinkers/skills" -name SKILL.md -exec grep -h "^name:" {} + | awk "{print \$2}" | sort -u)
   comm -12 <(echo "$existing") <(echo "$incoming")
   '
   ```
   Matrix includes built-in web and UI template skills; verify that no naming collisions exist.

2. **Install The Overthinkers skills into Hermes**:
   ```bash
   matrix run --project=main -C overthinkers -- bash -lc '
   mkdir -p ~/.hermes/skills
   cp -r skills/* ~/.hermes/skills/
   '
   ```

3. **(Optional) Install companion wearable skills**:
   To ingest Apple Health, Whoop, or Oura data alongside Samsung and Garmin, optionally clone and copy companion skills from `pridiuksson/highlander-longevity-coach`:
   ```bash
   matrix run --project=main -C . -- bash -lc '
   if [ ! -d ~/highlander-longevity-coach ]; then
     git clone https://github.com/pridiuksson/highlander-longevity-coach.git ~/highlander-longevity-coach 2>/dev/null || true
   fi
   if [ -d ~/highlander-longevity-coach/skills ]; then
     cp -r ~/highlander-longevity-coach/skills/* ~/.hermes/skills/ 2>/dev/null || true
   fi
   '
   ```

4. **Run repository quality gates & automated test suite**:
   ```bash
   # Leak scan (zero biometric values, zero credentials)
   matrix run --project=main -C overthinkers -- ./scripts/leak-scan.sh .

   # Skill structural integrity check
   matrix run --project=main -C overthinkers -- python3 scripts/validate-skills.py .

   # Full automated test suite (30 unit tests across Gates 0-3)
   matrix run --project=main -C overthinkers -- python3 -m unittest discover tests
   ```
   Expect `PASS` from `leak-scan.sh`, `OK` from `validate-skills.py`, and `Ran 30 tests ... OK`.

5. **Restart the Hermes gateway**:
   ```bash
   matrix run --project=main -C . -- bash -lc '
   hermes gateway restart
   hermes gateway status
   hermes skills list
   '
   ```

### B6 — configure runtime paths and preserve profiles

Use the shared installer; do not overwrite personalized profiles with `cp`:

```bash
python3 ~/overthinkers/scripts/install_runtime.py --dry-run
python3 ~/overthinkers/scripts/install_runtime.py
hermes skills list
```

Defaults use `HERMES_HOME` or `~/.hermes`, with data in `data/`, persona at `SOUL.md`, and context/memory in `memories/`. Set the same home and data paths for Hermes and all helper processes. Follow [ONBOARDING.md sections 5–8](../../ONBOARDING.md#5-install-profiles-and-use-one-runtime-home) for Telegram secrets, timezone, daily delivery, and the supervised reply worker. The current runner performs deterministic triage; a Hermes chat is a separate model session.

### B7 — create the Hermes Agent Desktop App & Icon (Matrix OS GUI)

Matrix OS desktop icons are discovered from manifests in `~/apps/<slug>/matrix.json` and placed
via the OS view state (`/api/os-view-state`). To add a dedicated **Hermes Agent** app icon to your
Matrix desktop:

1. **Deploy the desktop icon asset**:
   ```bash
   matrix run --project=main -C . -- bash -lc \
     'cp /opt/matrix/app/shell/public/agent-logos/hermes-agent.png ~/system/icons/hermes.png'
   ```

2. **Deploy and build The Overthinkers Control Center app**:
   ```bash
   matrix run --project=main -C . -- bash -lc '
   # Copy the full app package shipped in this repository
   cp -r ~/overthinkers/Box/Matrix/app ~/apps/hermes

   # Generate live telemetry status from your configuration and ledger
   python3 ~/overthinkers/scripts/generate_matrix_status.py

   # Build production assets
   cd ~/apps/hermes && npm install && npm run build
   '
   ```

3. **Pin to Desktop**:
   Add the app entry (`apps/hermes/index.html`) to the desktop icon grid via the OS-view state API
   or using the `add_app_to_desktop` tool in Matrix OS. The icon will appear live on your Matrix desktop.

### B8 — connect WhatsApp & enable Gemini 3.8 Voice Gateway

The Overthinkers operates seamlessly over WhatsApp using Hermes's built-in Baileys bridge and Google Gemini 3.8 for instantaneous voice transcription (STT) and voice note responses (TTS):

1. **Configure WhatsApp port & permissions on Matrix OS**:
   ```bash
   matrix run --project=main -C . -- bash -lc '
   # Route bridge to port 3010 to prevent collision with Matrix OS web desktop on port 3000
   hermes config set platforms.whatsapp.bridge_port 3010
   hermes config set platforms.whatsapp.enabled true
   hermes config set approvals.mode off
   echo "HERMES_YOLO_MODE=1" >> ~/.hermes/.env
   echo "HERMES_ACCEPT_HOOKS=1" >> ~/.hermes/.env
   '
   ```

2. **Enable Gemini 3.8 Flash STT & TTS**:
   ```bash
   matrix run --project=main -C . -- bash -lc '
   hermes tools enable stt
   hermes tools enable tts
   hermes config set tts.provider gemini
   hermes config set tts.gemini.model gemini-3.8-flash-tts
   hermes config set tts.gemini.voice Kore
   '
   ```

3. **Pair your WhatsApp account**:
   Run the pairing helper script and scan the QR code from WhatsApp on your phone (**Settings → Linked Devices → Link a Device**):
   ```bash
   matrix run --project=main -C . -- bash -lc '~/overthinkers/scripts/pair_whatsapp.sh'
   ```

4. **Restart gateway**:
   ```bash
   matrix run --project=main -C . -- bash -lc 'hermes gateway restart'
   ```

### B9 — ⛔ handback (human takes over)

The automated box setup is complete. The remaining steps are personal:

1. **Configure Personal Context**:
   Review and customize `~/.hermes/memories/USER.md` with your wearable setup, training patterns, and quiet hours.
2. **First Run & Gate Verification**:
   Launch an interactive terminal via `matrix shell` or the Matrix web console:
   ```bash
   # Test Gate 0 Steel Thread trigger simulation
   python3 ~/overthinkers/scripts/simulate_trigger.py --metric hrv --deviation -2.2 --interactive

   # Test Gate 3 Outcome Ledger recap
   python3 ~/overthinkers/scripts/orchestrator.py --recap

   # Launch interactive Hermes session
   hermes
   ```
   Test the prompt:
   *"Morning. Biometrics show an autonomic dip. Looking at things from the outside, what's taking up your bandwidth?"*
   Verify that Hermes engages the 80/20 behavioral coaching loop:
   - Self-distanced 3rd-person observer framing
   - Cognitive appraisal triage (Distress vs. Eustress vs. Recovery Drain)
   - Bounded single micro-action commitment
   - Strict $\le 3$ turn ceiling and anti-rumination circuit breaker
   - Automatic logging to the closed-loop outcome ledger in `$HERMES_HOME/data/ledger.db`

### B9 — daily delivery and supervised replies

Schedule `python3 ~/overthinkers/scripts/orchestrator.py --channel telegram` once each local morning using the configured scheduler. Run `python3 ~/overthinkers/scripts/orchestrator.py --watch` under a process supervisor. Both processes must inherit the same `HERMES_HOME`, `STRESS_TIMEZONE`, and private Telegram environment variables. See [ONBOARDING.md](../../ONBOARDING.md#7-configure-telegram-delivery-and-replies) for the complete setup and live acceptance checks.

## Teardown

If you want to decommission or reset the Matrix box:

1. **Remove repository and local health data**:
   ```bash
   matrix run --project=main -C . -- bash -lc 'rm -rf ~/health ~/overthinkers'
   ```
2. **Restart the instance**:
   ```bash
   matrix instance restart
   ```
3. To delete the computer completely, use the Matrix OS web console at `https://app.matrix-os.com`.

---

## Troubleshooting

| Symptom | Cause | Remedy |
|---|---|---|
| `npm install -g @finnaai/matrix` fails with `node-gyp rebuild` / `fsevents` | `fsevents` is macOS-only; npm attempts building optional dependencies | Install in isolated prefix `~/.local/share/finnaai-matrix` with `--prefix` (A2) |
| `curl -fsSL https://get.matrix-os.com` returns 404 | Standalone install script URL moved or deprecated | Use the npm installation method (A2) |
| `matrix run` exits 1 with `Request failed` | CLI v0.3.21 bug sends `cwd: ""` which fails backend schema validation | Always specify `--project=main -C .` (e.g. `matrix run --project=main -C . -- <cmd>`) |
| `matrix run` reports file or dir not found when using `~` | Local shell expanded `~` to local home instead of remote `$HOME` | Wrap remote command in quotes, use `bash -lc '...'`, or use `$HOME` |
| `matrix run` fails with HTTP 504 `upstream unavailable` | Single command exceeded Cloudflare / gateway HTTP timeout (~30–60s) | Break long tasks into discrete commands or run them inside an interactive `matrix shell` |
| `gitleaks` missing | Binary not yet installed on Matrix machine | Run B1 commands to download and install gitleaks 8.30.1 into `/usr/local/bin` |
| Gateway does not see new skills after copy | Skill catalogue is cached in memory | Run `hermes gateway restart` and verify with `hermes gateway status` (B5) |
| `hermes -z` fails with `not connected to any AI provider` | Model credentials missing on fresh install | Complete stop-point B3 (`hermes model` or `OPENROUTER_API_KEY` in `~/.hermes/.env`) |
