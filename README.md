# Asta

A personal AI workspace that runs on **desktop (macOS/Windows)** and **Telegram** with one shared context, persistent chat history, and multi-user support.

## Preview

![Asta UI preview](./preview.png)

## Why Asta

- **Cross-platform desktop app** — Tauri-based app (macOS + Windows) with sidebar conversation history, agent picker, PDF generation, and Tailscale remote access. Global shortcut `Alt+Space` to toggle.
- **Multi-user authentication** — JWT-based login with admin/user roles, self-registration, and per-user memories. Role-based access control across all endpoints and tools.
- Multi-provider AI: Groq, Google Gemini, Claude, OpenAI, OpenRouter, and Ollama.
- OpenClaw-style skill flow: model selects the best workspace skill and reads its `SKILL.md` on demand.
- Built-in skills: time/weather, web search, Spotify, reminders, audio notes, PDF generation, background learning, and Google Workspace (Gmail, Calendar, Drive via gog CLI).
- Clear split between **built-in Python skills** (core/reliable) and **workspace `SKILL.md` skills** (import/custom).
- Unified memory: persistent chat history (per-session), allowed local files, learned knowledge (RAG), and channel history.
- **Automated releases**: GitHub Actions builds macOS (DMG) and Windows (MSI) on version tags, published to GitHub Releases.
- Native setup: no Docker required.

## Requirements

- **Backend:** Python 3.12 or 3.13 (see `backend/requirements.txt`). Python 3.14 is not yet supported (pydantic/ChromaDB).
- **Desktop App:** Node 18+ and Rust toolchain (for Tauri).
- **Optional:** Ollama for local AI and RAG embeddings (`ollama pull nomic-embed-text`).

## Quick Start

### 1. Clone and configure

```bash
git clone https://github.com/helloworldxdwastaken/asta.git
cd asta
cp .env.example backend/.env
```

Add API keys in `backend/.env` if needed.

### 2. Start with the control script (recommended)

Backend uses **Python 3.12 or 3.13** (auto-picked; 3.14 not supported). On first run, the script creates a venv and installs deps.

```bash
./asta.sh setup     # optional: create backend venv + frontend deps first
./asta.sh install   # optional: add 'asta' command to your path
asta start          # or: ./asta.sh start
```

Open:

- API docs: `http://localhost:8010/docs`

### 3. Manual start (alternative)

Backend needs **Python 3.12 or 3.13** (3.14 not yet supported by pydantic/ChromaDB). If you only have 3.14: `brew install python@3.12`.

```bash
# Backend
cd backend
python3.12 -m venv .venv   # or python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8010
```

If the panel shows "API off", start the backend first or use **Settings -> Run the API**.

## `asta.sh` Commands

| Command | Description |
| --- | --- |
| `./asta.sh start` | Start backend (frees port `8010` first) |
| `./asta.sh stop` | Stop backend |
| `./asta.sh restart` | Restart backend |
| `./asta.sh status` | Show backend process status |
| `./asta.sh doc` | Run safe diagnostics (setup + service checks) |
| `./asta.sh doc --fix` | Run diagnostics + auto-fix common setup/dependency issues |

## Core Features

- **Dashboard**: system overview — Brain (AI providers), Body (CPU/RAM/disk + model), Eyes (vision), Channels, Notes, Schedule (reminders + cron), Capabilities (skills count).
- **Responsive dashboard layout**: medium/smaller screens now use adaptive card/vitals breakpoints for readable panel cards and metrics.
- **Chat**: provider routing + automatic skill execution.
- **Chat UX**: inline copy actions for user/assistant messages and editable past user turns that rewind conversation history from the edit point before re-running.
- **Reasoning controls**: per-user **Thinking level** (`off/minimal/low/medium/high/xhigh`) and **Reasoning visibility** (`off/on/stream`) in Settings and Telegram commands. Now supports **OpenRouter Kimi/Trinity** (via `reasoning_effort` + auto-injected `<think>` tags) and Ollama. Stream mode now uses a dedicated message event state machine for chunk-time reasoning/assistant updates (with post-generation fallback when providers do not stream).
- **Strict final mode**: optional `final_mode=strict` in Settings to show only text inside `<final>...</final>` blocks (OpenClaw-style enforcement).
- **Web live streaming**: Chat UI uses `POST /api/chat/stream` (SSE) for real-time `assistant` and `reasoning` updates powered by OpenClaw-style stream lifecycle events (`message_start/text_delta/text_end/message_end`).
- **OpenClaw-style main provider flow**: fixed priority chain `Claude -> Google -> OpenRouter -> Ollama`, with per-provider runtime enable/disable controls and auto-disable on billing/auth failures.
- **Hybrid vision pipeline**: Telegram image turns run through a low-cost vision model first (default: OpenRouter Nemotron free), then your main agent model handles the final reply/tool flow using the extracted vision notes.
- **Tool-first execution**: structured tools for exec/files/reminders/cron, OpenClaw-style `process` background session management, and single-user subagent orchestration (`sessions_spawn/list/history/send/stop`).
- **Image generation fallback**: `image_gen` tool uses Gemini first and Hugging Face FLUX.1-dev fallback (provider-aware routing + 5 req/min guardrail). If a model incorrectly claims image tools are unavailable, backend now runs deterministic image fallback instead of returning a false denial.
- **Subagent control UX**: deterministic `/subagents` command flow (`list/spawn/info/send/stop`, optional `--wait` on send) plus conservative auto-spawn for explicit long/background requests (toggle: `ASTA_SUBAGENTS_AUTO_SPAWN`).
- **Files**: local knowledge files + allowed paths. User context (who you are) lives in per-user memory files (editable in Settings > Memories).
- **Learning**: "learn about X for Y minutes" (also: "research/study/become an expert on X") with retrievable context.
- **Schedule (Reminders + Cron)**: list, add, update, remove, and run recurring jobs or one-shot reminders. One-shot reminders (created via "Remind me at...") are now visible on the **Cron** page with a **One-Shot** badge for easier management.
- **Automated Voice Calls (Pingram)**: triggering reliable phone calls for reminders and jobs via NotificationAPI (integration: Pingram). Supports custom **Pingram Templates** and fallback to default messages. Configure your phone number and credentials in the **Channels** page.
- **Channels**: Telegram and Voice Calls (Pingram) integrations in one place.
- **Settings/Skills**: key management, fixed main-provider flow, model policy controls, toggles, and backend controls.
- **Vision controls in Settings**: preprocess toggle with fixed model `nvidia/nemotron-nano-12b-v2-vl:free` for UI consistency.

## Channel Setup

- Telegram: set `TELEGRAM_BOT_TOKEN` in `backend/.env` or configure it in **Channels**.
- Telegram bot commands: `/status`, `/exec_mode`, `/allow`, `/allowlist`, `/approvals` (inline `Once/Always/Deny` actions, with automatic post-approval continuation), `/think` (aliases: `/thinking`, `/t`), `/reasoning`, `/subagents`.
- Telegram markdown image replies (`![...](...)`) are sent as native media (photos/animations), including inline `data:image/...` payloads from image generation.
- Exec allowlist hardening: in `allowlist` mode, Asta accepts only a single direct command (no `|`, `&&`, `;`, redirects, command substitution, or multiline scripts), and blocks shell launchers (`bash`, `sh`, `zsh`, `pwsh`, `cmd`) even if manually allowlisted.
- Vision input is supported on **Telegram photos** and **desktop app** (drag-and-drop or attach button).
- Optional debugging: set `ASTA_SHOW_TOOL_TRACE=true` and `ASTA_TOOL_TRACE_CHANNELS=web` to append `Tools used: ...` on replies (Telegram footer is suppressed because it already shows proactive skill-status pings).

## Learning / RAG Setup

For learning, embeddings are required. Asta currently uses **Ollama** embeddings (`nomic-embed-text`).

```bash
./scripts/setup_ollama_rag.sh
./scripts/setup_ollama_rag.sh -i
```

Then run `ollama serve` (or open Ollama app). If Ollama is unavailable, learning/RAG endpoints are unavailable until it is running.

## Docs

- `docs/INSTALL.md`: full install and environment setup (Linux/macOS/Windows).
- `docs/ERRORS.md`: common issues and fixes.
- `docs/SPEC.md`: product behavior and implementation notes.
- `docs/SECURITY.md`: secret handling and security guidance.

## Desktop App

The cross-platform desktop app lives in `MACWinApp/asta-app/`. It's built with **Tauri v2** (Rust + React/TypeScript).

**Features:**
- Sidebar with persistent conversation history (click to reload any past chat)
- Agent picker in chat with category-based colored icons (selection stays on the same chat until changed)
- Agents hub in sidebar (below **New chat**) to search/add/remove/create agents
- Message actions in chat: copy under both sides, plus edit/re-run for past user turns
- PDF generation: ask Asta to create PDFs (contracts, reports, invoices) — downloads directly in chat
- Settings panel: API keys, providers, Tailscale remote access, Spotify
- Remote access via Tailscale: "Enable HTTPS Tunnel" sets up `tailscale serve` for a proper `https://machine.ts.net` link to share with other devices
- File drag-and-drop in chat
- Provider icons in model dropdown and message badges
- Global shortcut `Alt+Space` to show/hide the app from anywhere

**Releasing:**
```bash
# Bump version in VERSION, Cargo.toml, and tauri.conf.json, then:
git tag v1.4.2
git push origin main --tags
```
GitHub Actions automatically builds macOS DMG (Apple Silicon + Intel) and Windows MSI, then publishes them to [GitHub Releases](https://github.com/helloworldxdwastaken/asta/releases).

**Build:**
```bash
cd MACWinApp/asta-app
npm install
npx tauri build   # outputs DMG (macOS) or MSI (Windows)
```

**Dev:**
```bash
cd MACWinApp/asta-app
npm install
npx tauri dev
```

## Project Structure

```text
asta/
├── backend/           # FastAPI backend
├── MACWinApp/         # Cross-platform desktop app (Tauri + React/TypeScript)
│   └── asta-app/      # Tauri app source
│       ├── src/       # React frontend
│       └── src-tauri/ # Rust backend (Tauri commands)
├── scripts/           # helper scripts (RAG/Ollama setup)
├── docs/              # install, spec, errors, security
├── asta.sh            # start/stop/restart/status/doc
├── .env.example       # copy to backend/.env
├── preview.png        # README preview image
└── README.md
```

## License

Use and modify freely.
