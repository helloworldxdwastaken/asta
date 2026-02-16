# Asta — Product specification & implementation guide

**Purpose:** This document defines what Asta is, what it does, and how to build it. If something is not implemented yet, any developer (or AI) can read this and continue the work.

---

## 1. Vision

Asta is a **personal control plane**: one place to talk to AI (Google, Claude, Ollama, etc.), automate tasks, manage files and cloud storage, and communicate via WhatsApp (Beta) and Telegram. It has a **web control panel** to manage everything, and can **learn** topics over time (RAG) so you can ask it to become an “expert” on a subject and answer from that knowledge.

**Core idea:** You control things by chatting (WhatsApp (Beta), Telegram, or the panel). The bot reads your messages, runs tasks (files, Drive, learning, scheduled jobs), and uses the right AI backend to reply.

---

## 2. Features (implemented vs planned)

Use this as the source of truth. When you implement a feature, move it to “Implemented” and note where in the codebase it lives.

### 2.1 Implemented

- **Control panel** — `frontend/`: Dashboard, Chat, Files, Drive, Learning (RAG), Audio notes, Skills, Channels, **Cron**, Settings. Dashboard: Brain (AI providers), Body (CPU/RAM/disk, CPU model), Eyes (vision), Channels, Notes (latest `workspace/notes/*.md`), Schedule (pending reminders + recurring cron jobs), Capabilities (active skills count). Cron tab: list/delete/update recurring jobs (plus scheduler-backed run actions via tool); auto-updater creates "Daily Auto-Update" on startup when skill present. Settings → Auto-updater for schedule/timezone.
- **AI providers** — `backend/app/providers/`: Groq, Google (Gemini), Claude, OpenAI, OpenRouter, Ollama. Main runtime chain is fixed (OpenClaw-style) to `Claude -> Ollama -> OpenRouter`; users pick default + per-provider models in Settings. Set keys in Settings or `backend/.env`.
- **Hybrid vision pipeline (Telegram photos)** — Image turns are preprocessed by a vision-capable model first (default priority: OpenRouter → Claude → OpenAI; OpenRouter default model: `nvidia/nemotron-nano-12b-v2-vl:free`). The extracted analysis is then passed to the user’s main agent model for final reply and tool actions. Settings UI keeps the vision model fixed to Nemotron for consistency.
- **Unified context** — AI receives recent conversation, connected channels, ground-truth state (pending reminders count, location), allowed file paths, Drive summary (when connected), RAG snippets, time/weather/lyrics/Spotify context, and tool instructions. Workspace `SKILL.md` bodies are not pre-injected; they are read on demand via tool call. `backend/app/context.py`, `handler.py`.
- **Intent-based built-in skills** — `backend/app/skill_router.py`: only relevant built-in skills run per message (time, weather, lyrics, Spotify, etc.). Saves tokens; status in Telegram/WhatsApp shows only used skills (e.g. "🎵 Finding lyrics…"). Service handlers are gated by skill toggles.
- **OpenClaw-style workspace skill flow** — Context exposes `<available_skills>` (enabled workspace skills only). Model selects one relevant skill, calls `read(path)` for that skill’s `SKILL.md`, then follows it. This avoids context pollution from loading all enabled workspace skills.
- **Workspace skill host gating** — Skills declaring `metadata.openclaw.os` and `requires.bins` are runtime-gated by host OS + required binaries (OpenClaw-style). This keeps macOS-only skills (e.g. Apple Notes) out of Linux runtime prompts.
- **Notes behavior** — Default notes are markdown files in `workspace/notes/` (via `notes` skill). Apple Notes (`memo`) is only used when explicitly requested.
- **Structured tool loop** — Handler executes provider tool calls for exec/files/reminders/cron/read, appends tool results, and re-calls the same provider for final user text.
- **Single-user subagent orchestration (OpenClaw-style)** — Added `agents_list`, `sessions_spawn`, `sessions_list`, `sessions_history`, `sessions_send`, and `sessions_stop` tools. `sessions_spawn` creates an isolated child conversation that runs in background and announces completion back to the parent conversation/channel. Includes max-concurrency guard, per-spawn model/thinking overrides, and auto-archive timers for keep-mode runs.
- **Reliability guardrails for skipped tools** — Deterministic fallback paths handle scheduler list/remove and desktop/file-check intents when a tool-capable model skips tool calls, preventing fake "done/checked" responses.
- **Reasoning controls** — Per-user `thinking_level` (`off/minimal/low/medium/high/xhigh`) and `reasoning_mode` (`off/on/stream`) are stored in `user_settings`, exposed in Settings API/UI, and applied to provider calls/context instructions. Stream mode consumes provider text deltas for incremental reasoning status (OpenAI/Groq/OpenRouter), with post-generation fallback when a provider path cannot stream. Web chat also supports SSE streaming via `POST /api/chat/stream` (`assistant`/`reasoning`/`status` events). Optional `final_mode` (`off|strict`) enforces visibility to `<final>...</final>` content only.
- **Provider runtime state + failover** — Added `provider_runtime_state` with per-provider `enabled`, `auto_disabled`, and `disabled_reason`; fallback path auto-disables providers on billing/auth failures and skips disabled providers until re-enabled/cleared.
- **Time & Weather** — `backend/app/time_weather.py`: separate skills. Time in 12h AM/PM; weather with today/tomorrow forecast (Open-Meteo). User location from DB or workspace/USER.md; **location normalization** (e.g. `Holon,IL` → "Holon, Israel", `Chicago, USA` → "Chicago, United States") before geocoding so local time works.
- **Web search** — `backend/app/search_web.py`: ddgs multi-backend search (no API key). Triggered mainly on explicit search intent ("search for", "look up", "check the web", "latest"), with RAG prioritized first when relevant.
- **Lyrics** — `backend/app/lyrics.py`: LRCLIB (free). "Lyrics of X", "lyrics for X", follow-ups like "a song by Artist". Multiple query formats if first search fails.
- **Spotify** — `backend/app/spotify_client.py`, `services/spotify_service.py`: search (Client ID/Secret in Settings → Spotify or `.env`). Playback: OAuth connect, list devices, "play X on Spotify" with device picker. If no track matches, **artist search** and play via `context_uri=spotify:artist:...`. `GET /api/spotify/connect`, `/api/spotify/callback`, `/api/spotify/devices`, `POST /api/spotify/play`.
- **Reminders** — `backend/app/reminders.py`: "Wake me up at 7am", "remind me tomorrow at 8am to X", "remind me in 30 min", "alarm in 5 min to X", "timer 10 min", "set alarm for 2h". User timezone from location (DB or workspace/USER.md). Absolute-time reminders (like "at 7am") require location; if missing, Asta asks for location first instead of scheduling in UTC. Friendly message at trigger time (Telegram/WhatsApp or web). **OpenClaw-style internals**: one-shot reminders are stored as one-shot cron entries (`@at <ISO-UTC>`) and fired by the cron scheduler path. **On startup**, legacy pending reminder rows are migrated into one-shot cron entries before cron reload. **Post-reply validation**: if AI claims it set a reminder but the parser didn't match, a correction is appended.
- **Audio notes** — `backend/app/audio_transcribe.py`, `app/audio_notes.py`, `routers/audio.py`: Upload audio (meetings, voice memos); transcribe with faster-whisper (local; model choice: base/small/medium); format with default AI. `POST /api/audio/process` (multipart: file, instruction, whisper_model, async_mode). With `async_mode=1`, returns 202 + job_id; poll `GET /api/audio/status/{job_id}` for progress (transcribing → formatting → done). Meeting notes (when instruction is "meeting") are saved in DB so user can ask "last meeting?" in Chat; context injects recent saved meetings. Telegram: voice/audio and audio-from-URL with progress messages ("Transcribing…", "Formatting…"). UI shows progress bar. Dependencies: `faster-whisper`, `python-multipart` (see `backend/requirements.txt`).
- **WhatsApp bridge (Beta)** — `services/whatsapp/` (Baileys): receives messages, POSTs to `/api/incoming/whatsapp`, sends reply. Run with `ASTA_API_URL=http://localhost:8010 npm run start`.
- **Telegram bot** — `backend/app/channels/telegram_bot.py`: long polling when `TELEGRAM_BOT_TOKEN` set; same message handler as panel/WhatsApp. Built-in commands include `/status`, `/exec_mode`, `/allow`, `/allowlist`, `/approvals` (with inline `Once/Always/Deny` actions and automatic post-approval continuation), `/think` (aliases: `/thinking`, `/t`), `/reasoning`, `/subagents`.
- **File management** — `backend/app/routers/files.py`: list/read under `ASTA_ALLOWED_PATHS` and workspace. **Virtual root**: "Asta knowledge" (`README.md`, `CHANGELOG.md`, and `docs/*.md`). **User context** = workspace/USER.md only (name, location, timezone, preferences); location there is used for time, weather, and reminders if DB location is empty.
- **Google Drive** — Stub in `routers/drive.py`; OAuth and list can be wired next.
- **RAG / Learning** — `backend/app/rag/service.py`: Chroma + Ollama embeddings (`nomic-embed-text`). Status label: "Checking learned knowledge". `POST /api/rag/learn`, `POST /api/tasks/learn`.
- **Scheduled tasks** — `backend/app/tasks/scheduler.py`: APScheduler runtime. Learning jobs plus cron scheduler (`app/cron_runner.py`) for recurring and one-shot (`@at`) reminder jobs. Startup runs reminder migration + cron reload from DB. Cron executions are persisted in `cron_job_runs` for history.

### 2.2 Planned (next)

| Feature | Description | Notes |
|--------|-------------|--------|
| **Google Drive OAuth** | Full OAuth flow and list files in panel. | Stub in `routers/drive.py`; add token storage. |
| **Learning / RAG** | “Learn X for Y hours” (also: “research/study/become expert on X”) → ingest content (URLs, files, paste), chunk, embed (Ollama or API), store in vector DB. Answer questions using that knowledge. | Use LangChain/LlamaIndex or custom pipeline; scheduler runs ingestion for the requested duration. |
| **Install script** | One-command install.sh / install.ps1. | See docs/INSTALL.md for manual steps. |

### 2.3 Future ideas (document only)

- **Voice (TTS / live):** Real-time speech-to-text in Chat, TTS output (e.g. Piper or cloud APIs). (Audio upload → notes is implemented.)
- **Calendar:** Google Calendar — create events, reminders.
- **Email:** Gmail — read/send, summarize.
- **Browser automation:** Open URLs, fill forms (Playwright).
- **Multi-agent / skills:** Different “personas” or skills (e.g. “code”, “writing”, “research”).
- **Encryption:** Encrypt API keys and sensitive chat history at rest.
- **Backup/export:** Export conversations and RAG knowledge.

---

## 3. Architecture

### 3.1 High level

```
[ User ]
   | WhatsApp / Telegram / Web panel
   v
[ Asta Backend (FastAPI) ]
   | - Message router (which channel, which provider)
   | - Task queue (learn, schedule, file ops)
   | - RAG service (vector store + retrieval)
   v
[ External services ]
   - Google AI, Claude, Ollama
   - Google Drive, local filesystem
   - WhatsApp, Telegram APIs
```

### 3.2 Components

| Component | Tech | Responsibility |
|-----------|------|----------------|
| **API** | FastAPI (Python 3.11+) | REST + WebSocket; auth; route to providers and tasks. |
| **Panel** | React (Vite), TypeScript | Dashboard: chats, settings, file browser, Drive, learning jobs. |
| **AI adapters** | Python modules | One module per provider (Groq, Google, Claude, OpenAI, OpenRouter, Ollama); same interface: `chat(messages) -> response`. |
| **WhatsApp (Beta)** | Baileys bridge service | Receive/send messages; forward to core message handler. |
| **Telegram** | python-telegram-bot | Webhook or long polling; forward to core message handler. |
| **Files** | Python (pathlib, aiofiles) | Local file ops in allowed dirs; list, read, search. |
| **Google Drive** | Google Drive API + OAuth2 | List, search, download; optional upload. |
| **RAG / Learning** | LangChain or custom | Ingest (URLs, files, text), chunk, embed (Ollama or API), store in vector DB; retrieve + generate answers. |
| **Scheduler** | APScheduler | “Learn for X hours”, cron-like tasks, reminders. |
| **Data** | SQLite + vector store | SQLite for users, tasks, config; Chroma/FAISS/sqlite-vec for embeddings. |

### 3.3 Data model (conceptual)

- **Users / settings:** user_settings (mood, default_ai_provider, thinking_level, reasoning_mode), provider_models, provider_runtime_state (enabled/auto-disabled state + reason), skill_toggles, api_keys (stored keys: Groq, Gemini, etc., Spotify Client ID/Secret).
- **User location:** user_location (user_id, location_name, lat, lon) for timezone and weather.
- **Conversations:** id, user_id, channel (web | telegram | whatsapp), created_at.
- **Messages:** id, conversation_id, role (user | assistant), content, provider_used, created_at.
- **Tasks:** id, user_id, type (learn | schedule), payload (JSON), status, run_at.
- **Reminders:** pending one-shots live in `cron_jobs` as `cron_expr='@at <ISO-UTC>'`; sent history is persisted in `reminders` table (`status='sent'`) for notifications/history APIs.
- **Spotify:** spotify_user_tokens (user_id, refresh_token, access_token, expires_at); pending_spotify_play (user_id, track_uri, devices_json) for device picker.
- **RAG documents:** Chroma; chunks in vector store with metadata.

---

## 4. Implementation notes (for developers / AI)

### 4.1 Where to add things

- **New AI provider:** Implement `backend/app/providers/base.py` interface; add under `backend/app/providers/`. Register in provider registry.
- **New skill:** Add intent and label in `skill_router.py`, run in `handler.py` (set `extra`), context in `context.py`, and entry in `routers/settings.py` SKILLS.
- **WhatsApp:** `services/whatsapp/` (Node + Baileys) — receives messages, POSTs to backend `/api/incoming/whatsapp`; outbound reminders use `ASTA_WHATSAPP_BRIDGE_URL` + `/send`.
- **Telegram:** `backend/app/channels/telegram_bot.py` — long polling; same message handler as panel/WhatsApp.
- **Panel:** `frontend/` — React app; new pages under `src/pages/`, API client in `src/api/`.
- **RAG:** `backend/app/rag/` — ingest pipeline, embedding (Ollama or API), vector store; expose “learn” and “ask about topic” endpoints.
- **Scheduler:** `backend/app/tasks/` — APScheduler jobs; “learn for X hours” = enqueue ingestion job with end_time.

### 4.2 Exec + process tools (OpenClaw-style)

**Same as OpenClaw core flow:** the model uses the **exec tool** for commands and the **process tool** for long-running background sessions. When the user asks to check Apple Notes (or list Things, etc.), the model calls `exec` with a `command`; backend runs it and returns tool output. For long tasks, `exec` can return `status=running` + `session_id`, then `process` manages that session (`list/poll/log/write/kill/clear/remove`).

- **Tool flow:** `handler.py` passes tools (exec/process/files/read/reminders/cron) to tool-capable providers (OpenAI, Groq, OpenRouter, Claude, Google). If the response has `tool_calls`, Asta runs each tool, appends tool output, and re-calls the same provider. Final reply is the last `response.content`.
- **Vision flow:** For image turns, `handler.py` runs a dedicated vision preprocessor (`_run_vision_preprocessor`) and injects `[VISION_ANALYSIS ...]` into the user message. Final reasoning/tool execution remains on the main selected provider.
- **Allowlist:** Env `ASTA_EXEC_ALLOWED_BINS` plus DB `exec_allowed_bins_extra`. Enabling a skill that declares `required_bins` (e.g. Apple Notes) adds those bins. Binary is resolved with `resolve_executable()` (PATH plus `/opt/homebrew/bin`, `/usr/local/bin`, `~/.local/bin`).
- **Fallback:** We still parse `[ASTA_EXEC: command][/ASTA_EXEC]` in the reply, run the command, and re-call with the output (now guarded to exec-intent requests only). Main-provider failover order is fixed (`claude -> ollama -> openrouter`) and runtime-state-aware (manual disable + auto-disable on auth/billing). See `exec_tool.py`, `process_tool.py`, `provider_flow.py`, `providers/fallback.py`, `handler.py`.

### 4.3 Subagent orchestration tools (OpenClaw-style, single-user)

- **Tools:** `agents_list`, `sessions_spawn`, `sessions_list`, `sessions_history`, `sessions_send`, `sessions_stop`.
- **Spawn flow:** model calls `sessions_spawn(task, ...)` → handler immediately returns accepted (`runId`, `childSessionKey`) and starts background execution in an isolated child conversation.
- **Command UX:** deterministic `/subagents` commands are handled in-core (`list/spawn/info/send/stop/help`) so orchestration control works even when model tool-calling is inconsistent.
- **Send wait option:** `/subagents send <runId> <message> --wait <seconds>` (and `sessions_send.timeoutSeconds`) can wait for a direct follow-up reply, returning `completed` or `timeout`.
- **Auto-spawn policy:** explicit background requests (and clearly complex long multi-step prompts) can auto-spawn a subagent without waiting for model tool-calls; controlled by `ASTA_SUBAGENTS_AUTO_SPAWN`.
- **Isolation:** child runs use channel `subagent` and a dedicated queue key (`subagent:<child_conversation_id>`) so they do not block inbound web/Telegram/WhatsApp turn handling.
- **Lifecycle:** run metadata is persisted in `subagent_runs` (status/result/error/timestamps plus model/thinking overrides and archive state). On startup, unfinished runs are marked `interrupted`.
- **Concurrency cap:** `ASTA_SUBAGENTS_MAX_CONCURRENT` limits active running subagents; over-cap `sessions_spawn` calls return `busy`.
- **Per-run overrides:** `sessions_spawn` accepts `model` and `thinking` (`off|minimal|low|medium|high|xhigh`) and applies them to child runs (also reused by `sessions_send`).
- **Auto-archive:** `ASTA_SUBAGENTS_ARCHIVE_AFTER_MINUTES` controls timed cleanup for `cleanup=keep` child sessions (set `0` to disable).
- **Announce:** when a subagent ends, Asta writes an assistant update to the parent conversation and also sends it to Telegram/WhatsApp when applicable.

### 4.4 Security

- Never commit API keys. Use env vars or a secrets store; document in README.
- Restrict file access to configured directories (e.g. `ASTA_ALLOWED_PATHS`).
- Validate and sanitize all user input; rate-limit public endpoints (Telegram/WhatsApp).
- Prefer read-only Drive scope if only “see what’s on the drive” is needed.

### 4.5 Easy install (planned)

- **Native:** `./asta.sh start` runs backend + frontend after manual venv/npm install. **Planned:** one command (e.g. `install.sh` or `curl ... | sh`) that pulls from GitHub and installs dependencies (venv, pip, npm) so you can run `./asta.sh start` with minimal steps. Document in README and docs/INSTALL.md.

### 4.6 What “learn for X time” should do

1. User says: “Learn everything about Next.js for the next 2 hours.”
2. Backend creates a **learning job:** sources (e.g. list of URLs or “crawl from this seed”), duration (2 hours), topic label (“Next.js”).
3. Scheduler runs an **ingestion loop** for 2 hours: fetch content (crawl/read), chunk, embed, store in vector DB with topic metadata.
4. When user asks “How do I use App Router in Next.js?”, the **RAG path** filters by topic “Next.js”, retrieves chunks, and generates answer with the chosen AI provider.
5. Optional: “Become an expert” = same as above with longer duration and possibly more sources (docs, tutorials, etc.).

---

## 5. File layout (target)

```
asta/
├── docs/
│   ├── SPEC.md          # This file
│   ├── INSTALL.md       # Install on Mac/Linux/Windows
│   └── SECURITY.md      # Secrets, .env, what not to commit
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── handler.py   # Core message handler (context, AI, reminders, skills)
│   │   ├── subagent_orchestrator.py # Single-user subagent runtime + sessions tools
│   │   ├── context.py  # Build AI context (skills, time, weather, lyrics, etc.)
│   │   ├── skill_router.py  # Intent-based skill selection
│   │   ├── reminders.py # Parse, schedule, fire reminders
│   │   ├── lyrics.py    # LRCLIB lyrics search
│   │   ├── spotify_client.py # Spotify search + user OAuth playback
│   │   ├── time_weather.py  # Geocode, timezone, weather (Open-Meteo)
│   │   ├── search_web.py   # DuckDuckGo search
│   │   ├── providers/   # AI adapters
│   │   ├── channels/    # Telegram (WhatsApp via bridge)
│   │   ├── routers/     # chat, files, drive, rag, settings, spotify
│   │   ├── rag/         # Ingest, embed, retrieve
│   │   └── tasks/       # Scheduler (learning, reminders)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/       # Dashboard, Chat, Files, Drive, Learning, Settings, Skills
│   │   └── api/         # API client
│   ├── package.json
├── services/whatsapp/   # WhatsApp bridge (Node)
├── asta.sh              # Start/stop/restart backend + frontend
├── .env.example         # Template; copy to backend/.env
└── README.md
```

---

## 6. Changelog (spec)

- **Current (1.3.15):** OpenClaw-style workspace skill selection (`<available_skills>` + on-demand `read`), strict frontmatter metadata parsing for required bins, and structured tool loop across OpenAI/Groq/OpenRouter/Claude/Google/Ollama. Added structured `files`, `reminders`, and `cron` tools, OpenClaw-style `process` tool for background exec session management (`list/poll/log/write/kill/clear/remove`), and single-user subagent orchestration tools (`sessions_spawn/list/history/send/stop`, plus `agents_list`) with persisted lifecycle + completion announcements. Subagents include max-concurrency guard, per-spawn model/thinking overrides, and auto-archive timers for keep-mode sessions. Main-provider failover uses a fixed runtime chain (`claude -> ollama -> openrouter`) with provider runtime states (`enabled/auto_disabled/disabled_reason`) and auto-disable on billing/auth failures. Settings expose this fixed provider flow directly, with model policy hardened for reliability (OpenRouter restricted to Kimi/Trinity families; Ollama overrides restricted to locally detected tool-capable models). Thinking/reasoning controls remain in Settings + Telegram (`/think` with `/thinking`/`/t` aliases, plus `/reasoning`) with levels `off/minimal/low/medium/high/xhigh`. Reasoning stream mode supports live delta-driven updates on OpenAI/Groq/OpenRouter provider paths and web SSE event streaming via `/api/chat/stream`, with code-safe reasoning-tag extraction/parsing for partial and closed `<think>` blocks. Strict `<final>` mode (`final_mode=strict`) enforces output visibility to `<final>...</final>` content only (including stream-time assistant text). Cron tool parity includes `run`, `runs`, and `wake` actions with normalized flattened argument recovery and persisted `cron_job_runs` history. Hybrid vision preprocessing remains enabled for Telegram photos (vision model first, main model final response), with Settings UI fixed to Nemotron for consistent vision behavior. Dashboard and Settings UI include additional medium/small-screen hardening and provider-flow load resilience. Skills catalog/runtime dedupe colliding IDs to prevent duplicate or missing cards in the Skills UI. Drive OAuth is still planned.
