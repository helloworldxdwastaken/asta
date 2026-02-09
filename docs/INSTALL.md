# Asta — Installation (macOS, Linux, Windows)

## How to install (pick one)

| Method | Steps |
|--------|--------|
| **Native (dev)** | 1) Copy `.env.example` → `backend/.env`. 2) Backend: `cd backend && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && uvicorn app.main:app --reload --port 8000`. 3) Frontend (new terminal): `cd frontend && npm install && npm run dev`. |
| **Docker** | 1) Copy `.env.example` → `.env` at repo root. 2) `docker compose up -d`. Panel: http://localhost:5173, API: http://localhost:8000. |

**Important:** For native install the backend reads **`backend/.env`** (not `.env` at root). For Docker, use `.env` at repo root (compose passes it to the container).

**If the API is down:** From the repo root run `./asta.sh start` (Linux/macOS) or start the backend manually (see "Native install" below). The panel shows "API off" when it cannot reach the backend; **Settings → Run the API** in the panel has the exact commands.

---

## Quick start with Docker (all platforms)

1. Clone or download Asta, then:

```bash
cd asta   # or your repo folder name (e.g. Clawd)
cp .env.example .env
# Edit .env and add your API keys (see below)
docker compose up -d
```

2. Open the panel: **http://localhost:5173** (or the port in `docker-compose.yml`).
3. API: **http://localhost:8000**.

## Environment variables (.env)

Copy `.env.example` to **`backend/.env`** (native) or **`.env`** (Docker).

**Tip:** Many keys can also be set in the panel under **Settings → API keys** or **Settings → Spotify**. Those are stored in the local DB (`backend/asta.db`) and override `.env` for that key. Restart the backend after changing the Telegram token.

| Variable | Description | Required for |
|----------|-------------|--------------|
| `GROQ_API_KEY` / `GEMINI_API_KEY` / `GOOGLE_AI_KEY` | API keys | Groq / Google AI (Gemini) |
| `ANTHROPIC_API_KEY` | Anthropic API key | Claude |
| `OPENAI_API_KEY` | OpenAI API key | OpenAI |
| `OLLAMA_BASE_URL` | e.g. `http://localhost:11434` | Ollama (local) |
| `TELEGRAM_BOT_TOKEN` | From [@BotFather](https://t.me/BotFather) | Telegram bot |
| `ASTA_ALLOWED_PATHS` | Comma-separated dirs for file access | File management |
| `ASTA_CORS_ORIGINS` | Extra origins (e.g. LAN or Tailscale URL) | Panel from another device |
| `ASTA_WHATSAPP_BRIDGE_URL` | e.g. `http://localhost:3001` | WhatsApp outbound (reminders, etc.) |
| `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` | From [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) | Spotify search & playback (or set in Settings → Spotify) |
| `ASTA_BASE_URL` | Your backend URL (e.g. `https://api.example.com`) | Spotify OAuth redirect (optional; for playback) |

**WhatsApp:** Run `services/whatsapp` with `ASTA_API_URL=http://localhost:8000`; scan QR in Settings.

**Audio notes:** No env vars needed. Transcription uses **faster-whisper** (local); formatting uses your default AI (set in Settings). Enable the skill in Settings → Skills and use the **Audio notes** page. Requires `pip install faster-whisper` and `python-multipart` (both in `backend/requirements.txt`). Meeting notes (when you choose that option) are saved so you can ask later e.g. “What was the last meeting about?” in Chat or Telegram.

**Reminders:** Scheduled reminders are stored in the DB and re-loaded into the scheduler on every backend startup. If you set a reminder and then restart the backend, it will still fire at the right time.

No key is required for the app to start; only the features you enable need keys.

## Backend dependencies (summary)

Install with `pip install -r backend/requirements.txt`. Key packages:

| Package | Purpose |
|--------|--------|
| fastapi, uvicorn, python-multipart | API server and form/file uploads (e.g. Audio notes) |
| faster-whisper | Local speech-to-text for Audio notes (no API key) |
| apscheduler | Reminders and scheduled tasks (jobs reloaded on startup) |
| aiosqlite | SQLite (conversations, reminders, settings, saved_audio_notes) |
| openai, google-generativeai, anthropic | AI providers (Groq, Gemini, Claude) |
| python-telegram-bot | Telegram bot |
| chromadb | RAG / learning (vector store) |

See **`backend/requirements.txt`** for full list and versions.

## Native install (no Docker)

### macOS / Linux

1. **Python 3.11+** and **Node 18+** installed.
2. **Create env file:** `cp .env.example backend/.env` then edit `backend/.env` with your keys (optional for first run).
3. Backend:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate   # Linux/macOS
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

4. Frontend (new terminal):

```bash
cd frontend
npm install
npm run dev
```

5. Open **http://localhost:5173** (panel) and **http://localhost:8000** (API docs).

6. **Optional:** In the panel, open **Settings** to add API keys (Groq, Gemini, Claude, Telegram, Spotify), set your default AI, and turn skills on/off (Time, Weather, Lyrics, Spotify, Reminders, Audio notes, Learning, Web search, etc.). Set your **location** (e.g. "Holon, Israel") in Chat so time and weather use your timezone. If the panel shows **API off**, use **Settings → Run the API** for the exact start commands.

### Windows

1. Install Python 3.11+ and Node 18+.
2. Create env file: `copy .env.example backend\.env` then edit `backend\.env` with your keys.
3. Backend:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

4. Frontend (new terminal):

```powershell
cd frontend
npm install
npm run dev
```

5. Open http://localhost:5173 (panel) and http://localhost:8000 (API docs).

6. **Optional:** In Settings, add API keys and configure skills (Time, Weather, Lyrics, Spotify, Reminders, etc.). Set your location in Chat for timezone-aware time and weather.

## Run the API (when it’s down)

If the panel shows **"API off"** or you get "Cannot reach Asta API":

1. **Linux / macOS (recommended):** From the repo root run:
   ```bash
   ./asta.sh start
   ```
2. **Or manually:** `cd backend`, activate your venv (`source .venv/bin/activate`), then:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
3. In the panel, **Settings → Run the API** shows these commands so you can copy-paste.

After the backend is running, the nav indicator will show **API** in green.

## Control script (Linux / macOS)

From the repo root you can use **`./asta.sh`** to start, stop, or restart the backend reliably (frees port 8000 and uses a PID file):

```bash
./asta.sh start     # start backend (stops anything on port first)
./asta.sh stop      # stop backend
./asta.sh restart   # stop then start (use after changing Telegram token, etc.)
./asta.sh status    # show if backend is running
```

The **Settings → "Restart backend"** button in the panel calls `./asta.sh restart` for you, so the backend comes back up cleanly after saving a new Telegram token.

## Troubleshooting

- **"Address already in use" (port 8000 or 5173)** — Run `./asta.sh restart` from the repo root to free the port and start fresh. Or stop the other process, or use a different port, e.g. `uvicorn app.main:app --reload --port 8001` and open `http://localhost:8001/docs`.
- **"Cannot reach Asta API" / "API off" in the panel** — Start the backend first: from repo root run `./asta.sh start`, or `cd backend && source .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000`. See **Settings → Run the API** in the panel for the exact commands. The panel proxies `/api` to `http://localhost:8000`.
- **Chat says "No AI provider available"** — Add at least one of: `GROQ_API_KEY`, `GEMINI_API_KEY`, or run Ollama locally and set `OLLAMA_BASE_URL` if needed.
- **Native install: backend can't find .env** — The backend reads **`backend/.env`** only. Run `cp .env.example backend/.env` from the repo root.
- **Lyrics / Spotify / Reminders not working** — Enable the skill in **Settings → Skills**. For Spotify, add Client ID and Secret in **Settings → Spotify** (or in `backend/.env`); for playback, click "Connect Spotify" once. For reminders, set your location in Chat (e.g. "I'm in Holon, Israel") so times use your timezone. **Reminders not firing?** Restart the backend once so pending reminders are re-loaded into the scheduler (`./asta.sh restart`).
- **Audio notes: "faster-whisper is not installed"** — Run `pip install -r requirements.txt` in the backend venv (includes `faster-whisper` and `python-multipart`). First run may download the Whisper model (~140 MB).

## Optional: one-line install script (future)

Planned: `install.sh` (Mac/Linux) and `install.ps1` (Windows) that create venv, install deps, copy `.env.example` to `backend/.env`, and print run commands. See SPEC.md.
