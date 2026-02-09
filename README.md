# Asta

**Personal control plane:** one place to talk to AI (Google, Claude, Ollama), automate tasks, manage files and Google Drive, and chat via **WhatsApp** and **Telegram**. The AI has **unified context**: conversation, channels, files, Drive (when connected), learned knowledge, **time & weather**, **web search**, **lyrics**, **Spotify** (search + play on your devices), **reminders** (wake me up, remind me at…), and **audio notes** (upload meetings/voice memos → transcript + meeting notes). Skills are intent-based and can be toggled in Settings.

## Features

| Feature | Status |
|--------|--------|
| Web control panel (Dashboard, Chat, Files, Drive, Learning, Settings, Skills) | Done |
| AI providers: Groq, Google Gemini, Claude, Ollama | Done — set keys in Settings or `backend/.env` |
| Unified context (conversation, channels, files, RAG, time, weather, lyrics, Spotify, reminders) | Done |
| Intent-based skills (only run what’s relevant; status in Telegram/WhatsApp) | Done |
| Time & Weather (12h AM/PM, forecast; set location once) | Done |
| Web search (DuckDuckGo, no key) | Done |
| Lyrics (LRCLIB; “lyrics of X”, “song by Artist”) | Done |
| Spotify (search + play on devices; OAuth in Settings) | Done |
| Reminders (“wake me up at 7am”, “remind me tomorrow at 8am to …”) | Done |
| Audio notes (upload/Telegram; progress bar; meeting notes saved for "last meeting?") | Done |
| Learning / RAG (Ollama + Chroma; "learned knowledge") | Done |
| WhatsApp bridge (whatsapp-web.js) | Done — run `services/whatsapp` or Docker profile `whatsapp` |
| Telegram bot | Done — set `TELEGRAM_BOT_TOKEN` |
| File management (allowed paths) | Done |
| Google Drive | Stub (OAuth to be wired) |
| Cross-platform | Docker + native; see `docs/INSTALL.md` |

## Quick start

**Docker (recommended)**

```bash
cp .env.example .env
# Edit .env if you have API keys
docker compose up -d
```

- Panel: **http://localhost:5173**
- API: **http://localhost:8000** · Docs: **http://localhost:8000/docs**

**Native (dev)**

```bash
cp .env.example backend/.env   # then edit backend/.env with your keys (optional at first)
# Backend (from repo root you can use ./asta.sh start instead)
cd backend && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && uvicorn app.main:app --reload --port 8000

# Frontend (other terminal)
cd frontend && npm install && npm run dev
```

Then open **http://localhost:5173**. If the panel shows "API off", start the backend (see **Settings → Run the API** in the panel or **docs/INSTALL.md**). Full steps (Windows too): **docs/INSTALL.md**.

## Docs

- **`docs/INSTALL.md`** — Install on macOS, Linux, and Windows (Docker and native).
- **`docs/SPEC.md`** — Product spec, architecture, and where to add features.
- **`docs/SECURITY.md`** — Keep API keys and secrets out of GitHub (use `backend/.env` only).

## Backend dependencies (key packages)

- **fastapi**, **uvicorn**, **python-multipart** — API and form/upload handling
- **faster-whisper** — local audio transcription (Audio notes; no API key)
- **apscheduler** — reminders and scheduled tasks (reloaded on startup)
- **aiosqlite** — SQLite DB (conversations, reminders, settings, saved meeting notes)
- See **`backend/requirements.txt`** for full list.

## Project layout

```
asta/
├── docs/              # INSTALL.md, SPEC.md, SECURITY.md
├── backend/           # FastAPI (Python) — reads backend/.env; API keys also in Settings (DB)
├── frontend/          # React + Vite (panel; includes Audio notes page)
├── services/whatsapp/ # WhatsApp bridge (Node)
├── asta.sh            # Start/stop/restart backend (Linux/macOS)
├── docker-compose.yml
├── .env.example       # template; copy to backend/.env (native) or .env (Docker)
└── README.md
```

## License

Use and modify as you like.
