# Asta — Product specification & implementation guide

**Purpose:** This document defines what Asta is, what it does, and how to build it. If something is not implemented yet, any developer (or AI) can read this and continue the work.

---

## 1. Vision

Asta is a **personal control plane**: one place to talk to AI (Google, Claude, Ollama, etc.), automate tasks, manage files and cloud storage, and communicate via WhatsApp and Telegram. It has a **web control panel** to manage everything, and can **learn** topics over time (RAG) so you can ask it to become an “expert” on a subject and answer from that knowledge.

**Core idea:** You control things by chatting (WhatsApp, Telegram, or the panel). The bot reads your messages, runs tasks (files, Drive, learning, scheduled jobs), and uses the right AI backend to reply.

---

## 2. Features (implemented vs planned)

Use this as the source of truth. When you implement a feature, move it to “Implemented” and note where in the codebase it lives.

### 2.1 Implemented

- **Control panel** — `frontend/`: Dashboard, Chat, Files, Drive, Learning (RAG), Audio notes, Skills, Channels, **Cron**, Settings. Dashboard: Brain (AI providers), Body (CPU/RAM/disk, CPU model), Eyes (vision), Channels, Tasks, Schedule (cron count), Capabilities (active skills count). Cron tab: list/delete/update recurring jobs; auto-updater creates "Daily Auto-Update" on startup when skill present. Settings → Auto-updater for schedule/timezone.
- **AI providers** — `backend/app/providers/`: Groq, Google (Gemini), Claude, OpenAI, OpenRouter, Ollama. Set keys in Settings or `backend/.env`.
- **Unified context** — AI receives: recent conversation, connected channels, **ground-truth state** (pending reminder count, location), allowed file paths, Drive summary (when connected), RAG snippets, time, weather, lyrics, Spotify, reminders. When reminders skill is used, the **actual pending reminders list** is injected so the AI doesn't hallucinate. `backend/app/context.py`, `handler.py`.
- **Intent-based skills** — `backend/app/skill_router.py`: only relevant skills run per message (time, weather, lyrics, Spotify, etc.). Saves tokens; status in Telegram/WhatsApp shows only used skills (e.g. "🎵 Finding lyrics…"). Service-style handlers (reminders, learning, Spotify) are gated by skill toggles.
- **Time & Weather** — `backend/app/time_weather.py`: separate skills. Time in 12h AM/PM; weather with today/tomorrow forecast (Open-Meteo). User location from DB or workspace/USER.md; **location normalization** (e.g. `Holon,IL` → "Holon, Israel", `Chicago, USA` → "Chicago, United States") before geocoding so local time works.
- **Web search** — `backend/app/search_web.py`: ddgs multi-backend search (no API key). Triggered mainly on explicit search intent ("search for", "look up", "check the web", "latest"), with RAG prioritized first when relevant.
- **Lyrics** — `backend/app/lyrics.py`: LRCLIB (free). "Lyrics of X", "lyrics for X", follow-ups like "a song by Artist". Multiple query formats if first search fails.
- **Spotify** — `backend/app/spotify_client.py`, `services/spotify_service.py`: search (Client ID/Secret in Settings → Spotify or `.env`). Playback: OAuth connect, list devices, "play X on Spotify" with device picker. If no track matches, **artist search** and play via `context_uri=spotify:artist:...`. `GET /api/spotify/connect`, `/api/spotify/callback`, `/api/spotify/devices`, `POST /api/spotify/play`.
- **Reminders** — `backend/app/reminders.py`: "Wake me up at 7am", "remind me tomorrow at 8am to X", "remind me in 30 min", "alarm in 5 min to X", "timer 10 min", "set alarm for 2h". User timezone from location (DB or workspace/USER.md). Absolute-time reminders (like "at 7am") require location; if missing, Asta asks for location first instead of scheduling in UTC. Friendly message at trigger time (Telegram/WhatsApp or web). APScheduler + DB. **On startup**, `reload_pending_reminders()` loads all pending reminders from DB. **Post-reply validation**: if AI claims it set a reminder but the parser didn't match, a correction is appended.
- **Audio notes** — `backend/app/audio_transcribe.py`, `app/audio_notes.py`, `routers/audio.py`: Upload audio (meetings, voice memos); transcribe with faster-whisper (local; model choice: base/small/medium); format with default AI. `POST /api/audio/process` (multipart: file, instruction, whisper_model, async_mode). With `async_mode=1`, returns 202 + job_id; poll `GET /api/audio/status/{job_id}` for progress (transcribing → formatting → done). Meeting notes (when instruction is "meeting") are saved in DB so user can ask "last meeting?" in Chat; context injects recent saved meetings. Telegram: voice/audio and audio-from-URL with progress messages ("Transcribing…", "Formatting…"). UI shows progress bar. Dependencies: `faster-whisper`, `python-multipart` (see `backend/requirements.txt`).
- **WhatsApp bridge** — `services/whatsapp/` (Baileys): receives messages, POSTs to `/api/incoming/whatsapp`, sends reply. Run with `ASTA_API_URL=http://localhost:8010 npm run start`.
- **Telegram bot** — `backend/app/channels/telegram_bot.py`: long polling when `TELEGRAM_BOT_TOKEN` set; same message handler as panel/WhatsApp.
- **File management** — `backend/app/routers/files.py`: list/read under `ASTA_ALLOWED_PATHS` and workspace. **Virtual root**: "Asta knowledge" (README + docs/*.md). **User context** = workspace/USER.md only (name, location, timezone, preferences); location there is used for time, weather, and reminders if DB location is empty.
- **Google Drive** — Stub in `routers/drive.py`; OAuth and list can be wired next.
- **RAG / Learning** — `backend/app/rag/service.py`: Chroma + Ollama embeddings (`nomic-embed-text`). Status label: "Checking learned knowledge". `POST /api/rag/learn`, `POST /api/tasks/learn`.
- **Scheduled tasks** — `backend/app/tasks/scheduler.py`: APScheduler; learning jobs and reminder fire times. Reminders are re-loaded from DB on startup (`app/reminders.py`: `reload_pending_reminders()` called from `main.py` lifespan).

### 2.2 Planned (next)

| Feature | Description | Notes |
|--------|-------------|--------|
| **Google Drive OAuth** | Full OAuth flow and list files in panel. | Stub in `routers/drive.py`; add token storage. |
| **Recurring reminders / cron** | "Every day at 9", "every Monday at 5pm". | One-off reminders done; add recurring. |
| **Google Drive** | Connect to Google Drive (OAuth2), list files, search, download, optionally upload. Show “what’s on the drive” in panel. | Google Drive API + OAuth; store tokens securely. |
| **Learning / RAG** | “Learn X for Y hours” → ingest content (URLs, files, paste), chunk, embed (Ollama or API), store in vector DB. Answer questions using that knowledge. | Use LangChain/LlamaIndex or custom pipeline; scheduler runs ingestion for the requested duration. |
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
| **WhatsApp** | Baileys bridge service | Receive/send messages; forward to core message handler. |
| **Telegram** | python-telegram-bot | Webhook or long polling; forward to core message handler. |
| **Files** | Python (pathlib, aiofiles) | Local file ops in allowed dirs; list, read, search. |
| **Google Drive** | Google Drive API + OAuth2 | List, search, download; optional upload. |
| **RAG / Learning** | LangChain or custom | Ingest (URLs, files, text), chunk, embed (Ollama or API), store in vector DB; retrieve + generate answers. |
| **Scheduler** | APScheduler or Celery | “Learn for X hours”, cron-like tasks, reminders. |
| **Data** | SQLite + vector store | SQLite for users, tasks, config; Chroma/FAISS/sqlite-vec for embeddings. |

### 3.3 Data model (conceptual)

- **Users / settings:** user_settings (mood, default_ai_provider), provider_models, skill_toggles, api_keys (stored keys: Groq, Gemini, etc., Spotify Client ID/Secret).
- **User location:** user_location (user_id, location_name, lat, lon) for timezone and weather.
- **Conversations:** id, user_id, channel (web | telegram | whatsapp), created_at.
- **Messages:** id, conversation_id, role (user | assistant), content, provider_used, created_at.
- **Tasks:** id, user_id, type (learn | schedule), payload (JSON), status, run_at.
- **Reminders:** id, user_id, channel, channel_target, message, run_at, status (pending | sent). APScheduler fires at run_at and sends via Telegram/WhatsApp or web.
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

### 4.2 Security

- Never commit API keys. Use env vars or a secrets store; document in README.
- Restrict file access to configured directories (e.g. `ASTA_ALLOWED_PATHS`).
- Validate and sanitize all user input; rate-limit public endpoints (Telegram/WhatsApp).
- Prefer read-only Drive scope if only “see what’s on the drive” is needed.

### 4.3 Easy install (planned)

- **Native:** `./asta.sh start` runs backend + frontend after manual venv/npm install. **Planned:** one command (e.g. `install.sh` or `curl ... | sh`) that pulls from GitHub and installs dependencies (venv, pip, npm) so you can run `./asta.sh start` with minimal steps. Document in README and docs/INSTALL.md.

### 4.4 What “learn for X time” should do

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

- **Current (1.1.0):** Control panel (Dashboard, Chat, Files, Drive, Learning, Audio notes, Skills, Channels, **Cron**, Settings). **Cron** tab: list/delete/update jobs; auto-updater skill creates Daily Auto-Update on startup; Settings → Auto-updater. **Dashboard**: 4-col layout, Brain|Body|Eyes top row, Schedule (cron count), Capabilities (active skills count); CPU model + cores in Body; Ollama shows only installed models. **Time**: USER.md location normalized (country codes, strip italics) for geocoding → local time. **Spotify**: play artist when no track found (artist search + context_uri). Recurring jobs via cron; one-off reminders unchanged. Drive OAuth planned.
