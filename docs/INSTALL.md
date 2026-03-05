# Asta — Installation (macOS, Linux, Windows)

**Native install only** (no Docker). You need **Python 3.12 or 3.13** (3.14 not yet supported by pydantic/ChromaDB). The primary UI is the **desktop app** (`MACWinApp/asta-app/`) — a cross-platform Tauri app that runs on macOS and Windows. Supports multi-user authentication with admin/user roles.

---

## Quick start (Linux / macOS)

```bash
git clone https://github.com/helloworldxdwastaken/asta.git
cd asta
cp .env.example backend/.env
# Edit backend/.env with your keys (optional at first)

./asta.sh start
```

Open **http://localhost:8010/docs** for API docs. Connect the desktop app to `http://localhost:8010`.

---

## Manual steps (all platforms)

### 1. Env file

Copy `.env.example` to **`backend/.env`** and add API keys (optional for first run). The backend reads **`backend/.env`** only.

### 2. Backend (macOS / Linux)

Use **Python 3.12 or 3.13** (e.g. `brew install python@3.12`). Then:

```bash
cd backend
python3.12 -m venv .venv   # or python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8010
```

### 3. Desktop app

The desktop app is built with **Tauri v2** (Rust + React/TypeScript). To run in dev mode:

```bash
cd MACWinApp/asta-app
npm install
npx tauri dev
```

To build a release (DMG on macOS, MSI on Windows):

```bash
cd MACWinApp/asta-app
npx tauri build
```

Connect the app to `http://localhost:8010` in Settings → Connection.

### 4. Multi-user setup

On first run with no users in the database, Asta operates in **single-user mode** (open access, no login required). To enable multi-user authentication:

1. Create the first admin user via the API (while in single-user mode):
   ```bash
   curl -X POST http://localhost:8010/api/auth/users \
     -H "Content-Type: application/json" \
     -d '{"username": "admin", "password": "your-password", "role": "admin"}'
   ```
2. The desktop app will now show a **login screen**. Sign in with the admin credentials.
3. Admin can create additional users from **Settings > Users** or users can self-register via the login page.

**Roles:**
- **Admin** — Full access: all settings, skills, tools, agents, and user management.
- **User** — Chat access with safe tools (web search, weather, math, GIFs, PDF, time). No settings, no agents, no exec/files/reminders.

**JWT secret:** Auto-generated on first login and stored in `backend/.env` as `ASTA_JWT_SECRET`. Tokens expire after 30 days.

### 5. Optional

In the desktop app: **Settings** → add API keys (Groq, Gemini, Claude, OpenAI, OpenRouter, Hugging Face, Telegram, Spotify), set default AI (main runtime chain is fixed to `Claude -> Google -> OpenRouter -> Ollama`), choose **Thinking level** (`off/minimal/low/medium/high/xhigh`), **Reasoning visibility** (`off/on/stream`), and **Final tag mode** (`off/strict`), adjust **Vision controls** (preprocess toggle with fixed Nemotron model), and toggle skills. Set your **location** in Chat (e.g. "Holon, Israel") for time and weather.

**Telegram commands:** `/status`, `/exec_mode`, `/allow`, `/allowlist`, `/approvals` (inline `Once/Always/Deny` actions, with automatic post-approval continuation), `/think` (aliases: `/thinking`, `/t`), `/reasoning`, `/subagents`.
`/reasoning stream` emits live reasoning status on OpenAI/Groq/OpenRouter provider paths.

**Apple Notes (macOS):** See the **Apple Notes** skill on the **Skills** page: it shows the install command (`brew tap … && brew install …`) and automatically adds `memo` to the exec allowlist when you enable the skill (no need to edit `.env`). When you ask Asta to check your notes, the AI runs the command via the exec tool and replies from the output. **Permission is per process:** Run the **Asta backend from Terminal** (e.g. `./asta.sh start`). The first time you ask to check notes, a macOS dialog may appear — approve it so the **backend process** (not just Terminal) can run memo. If you only ran `memo notes` in Terminal before, that approved Terminal; the backend is a different process and needs its own approval.

---

## Windows

1. **Env:** `copy .env.example backend\.env` then edit `backend\.env`.
2. **Backend:**

   ```powershell
   cd backend
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8010
   ```

3. **Desktop app:**

   ```powershell
   cd MACWinApp\asta-app
   npm install
   npx tauri dev     # dev mode
   npx tauri build   # release (MSI installer)
   ```

4. Open **http://localhost:8010/docs** for API docs. The desktop app connects to `http://localhost:8010` by default.

---

## Control script (Linux / macOS)

From the repo root, **`./asta.sh`** starts/stops the backend:

```bash
./asta.sh start     # start backend (frees port first)
./asta.sh stop      # stop backend
./asta.sh restart   # stop then start (e.g. after changing Telegram token)
./asta.sh status    # show if backend is running
./asta.sh doc       # run safe diagnostics (setup + service checks)
./asta.sh doc --fix # run diagnostics + auto-fix common setup/dependency issues
```

**Settings → Restart backend** in the desktop app runs `./asta.sh restart`.

---

## Environment variables (`backend/.env`)

| Variable | Purpose |
|----------|--------|
| `GROQ_API_KEY` / `GEMINI_API_KEY` / `GOOGLE_AI_KEY` | Groq / Google AI |
| `ANTHROPIC_API_KEY` | Claude |
| `OPENAI_API_KEY` | OpenAI |
| `OPENROUTER_API_KEY` | OpenRouter |
| `HUGGINGFACE_API_KEY` | Hugging Face image fallback (FLUX.1-dev via inference providers) |
| `OLLAMA_BASE_URL` | e.g. `http://localhost:11434` (Ollama) |
| `TELEGRAM_BOT_TOKEN` | Telegram bot ([@BotFather](https://t.me/BotFather)) |
| `ASTA_ALLOWED_PATHS` | Comma-separated dirs for file access |
| `ASTA_EXEC_ALLOWED_BINS` | Exec tool: binaries Asta can run (e.g. `memo`, `things`). Optional: skills like Apple Notes show install steps on the Skills page and can auto-add the bin when enabled. |
| `ASTA_PROCESS_TTL_SECONDS` | Keep finished background process sessions in memory for process tool (`list/poll/log`) before cleanup (default: 1800). |
| `ASTA_SUBAGENTS_AUTO_SPAWN` | Enable deterministic auto-spawn for explicit/complex long-task prompts (default: `true`). |
| `ASTA_SUBAGENTS_MAX_CONCURRENT` | Max concurrent subagent runs from `sessions_spawn` (default: `3`). |
| `ASTA_SUBAGENTS_MAX_DEPTH` | Maximum subagent nesting depth (default: `1`, meaning no nested subagents). |
| `ASTA_SUBAGENTS_MAX_CHILDREN` | Maximum concurrent children per parent subagent run (default: `5`). |
| `ASTA_SUBAGENTS_ARCHIVE_AFTER_MINUTES` | Auto-archive keep-mode subagent child sessions after N minutes (default: `60`, set `0` to disable). |
| `ASTA_VISION_PREPROCESS` | Run hybrid vision flow: image analyzed by vision provider first, then main agent answers from analysis (default: `true`). |
| `ASTA_VISION_PROVIDER_ORDER` | Advanced override for vision provider priority (default: `openrouter,claude,openai`). Settings UI keeps this fixed. |
| `ASTA_VISION_OPENROUTER_MODEL` | Advanced override for vision preprocessor model (default: `nvidia/nemotron-nano-12b-v2-vl:free`). Settings UI keeps this fixed. |
| `ASTA_JWT_SECRET` | JWT signing secret (auto-generated on first login if not set) |
| `ASTA_CORS_ORIGINS` | Extra origins (e.g. LAN or Tailscale) |
| `ASTA_OWNER_PHONE_NUMBER` | Default E.164 phone for Pingram reminder/job voice calls (e.g. `+15551234567`). |
| `ASTA_PINGRAM_CLIENT_ID` / `ASTA_PINGRAM_CLIENT_SECRET` / `ASTA_PINGRAM_API_KEY` | Pingram credentials (client pair or API key). |
| `ASTA_PINGRAM_NOTIFICATION_ID` / `ASTA_PINGRAM_TEMPLATE_ID` | Pingram sender notification/template IDs. |
| `ASTA_SHOW_TOOL_TRACE` | Append `Tools used: ...` footer (debug) |
| `ASTA_TOOL_TRACE_CHANNELS` | Trace footer channels, default `web` (Telegram footer suppressed; Telegram already gets skill-status pings) |
| `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` | Or set in Settings → Spotify |
| `ASTA_BASE_URL` | Backend URL for Spotify OAuth redirect (optional) |

Many keys can also be set in **Settings → API keys** or **Settings → Spotify**; those are stored in the local DB and override `.env`. Restart the backend after changing the Telegram token.

**Audio notes:** No extra env; uses faster-whisper (local). **Reminders:** Stored in DB and re-loaded on backend startup.

**Vision flow:** Telegram photos are supported. By default, Asta runs a low-cost vision model first, then gives that analysis to your selected main model for the final response/tool actions.

**Main AI provider flow:** runtime priority is fixed to `Claude -> Google -> OpenRouter -> Ollama` (OpenClaw-style). Billing/auth failures can auto-disable a provider until it is re-enabled from Settings (or key test succeeds).

---

## Run the API when it's down

If the panel shows **"API off"**:

1. **Linux / macOS:** From repo root run `./asta.sh start` (or `./asta.sh restart`).
2. **Or manually:** `cd backend`, activate venv, then `uvicorn app.main:app --host 0.0.0.0 --port 8010`.
3. **Settings → Run the API** in the panel shows the exact commands.

---

## Troubleshooting

See **docs/ERRORS.md** for a full list of common errors and fixes. Quick checks:

- **"Address already in use" (8010)** — Run `./asta.sh restart` to free the port and start fresh. Or use another port, e.g. `uvicorn app.main:app --reload --port 8001` and update `ASTA_API_URL` accordingly.
- **"Cannot reach Asta API" / "API off"** — Start the backend: `./asta.sh start` or run uvicorn as above. The desktop app connects to `http://localhost:8010` by default.
- **"No AI provider available"** — Add at least one of: `GROQ_API_KEY`, `GEMINI_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, or run Ollama and set `OLLAMA_BASE_URL`.
- **Backend can't find .env** — Backend reads **`backend/.env`** only. Run `cp .env.example backend/.env` from the repo root.
- **Lyrics / Spotify / Reminders** — Enable the skill in **Settings → Skills**. For Spotify, add Client ID and Secret in Settings → Spotify; for reminders, set location in Chat.
- **"Wake me up at 7am" asks for location first** — Expected when no location is set. Asta now requires location/timezone for absolute-time reminders.
- **Reminders not firing** — Restart the backend once so pending reminders are re-loaded (`./asta.sh restart`).
- **Audio notes: "faster-whisper is not installed"** — Run `pip install -r requirements.txt` in the backend venv. First run may download the Whisper model (~140 MB).

---

## Pre-built releases (recommended for end users)

Download the latest release from [GitHub Releases](https://github.com/helloworldxdwastaken/asta/releases):

- **macOS (Apple Silicon):** `Asta_<version>_aarch64.dmg`
- **macOS (Intel):** `Asta_<version>_x64.dmg`
- **Windows:** `Asta_<version>_x64-setup.msi`

Open the DMG/MSI, install, then start the backend separately (`./asta.sh start` or manually via Python).

---

## Releasing a new version

1. Bump the version number in three files:
   - `VERSION`
   - `MACWinApp/asta-app/src-tauri/Cargo.toml` (the `version` field)
   - `MACWinApp/asta-app/src-tauri/tauri.conf.json` (the `version` field)
2. Update `CHANGELOG.md` with the new version's changes.
3. Commit, tag, and push:
   ```bash
   git add -A && git commit -m "chore: bump version to X.Y.Z"
   git tag vX.Y.Z
   git push origin main --tags
   ```
4. GitHub Actions (`.github/workflows/release.yml`) automatically:
   - Builds macOS DMG (Apple Silicon + Intel) and Windows MSI
   - Creates a GitHub Release with all artifacts attached
   - Links to `CHANGELOG.md` in the release notes

You can also trigger the workflow manually from the Actions tab (`workflow_dispatch`).

---

## Easy install (planned)

Planned: a single command (e.g. `curl ... | sh` or `install.sh`) that pulls from GitHub and installs dependencies (Python venv, pip, Node/npm, Rust) so you can run `./asta.sh start` with minimal steps. See SPEC.md when available.
