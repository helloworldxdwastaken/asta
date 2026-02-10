# Asta — Installation (macOS, Linux, Windows)

**Native install only** (no Docker). You need **Python 3.11+** and **Node 18+**.

---

## Quick start (Linux / macOS)

```bash
git clone https://github.com/helloworldxdwastaken/asta.git
cd asta
cp .env.example backend/.env
# Edit backend/.env with your keys (optional at first)

./asta.sh start
```

Open **http://localhost:5173** (panel) and **http://localhost:8010/docs** (API docs).

---

## Manual steps (all platforms)

### 1. Env file

Copy `.env.example` to **`backend/.env`** and add API keys (optional for first run). The backend reads **`backend/.env`** only.

### 2. Backend (macOS / Linux)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8010
```

### 3. Frontend (new terminal)

```bash
cd frontend
npm install
npm run dev
```

### 4. Open

- Panel: **http://localhost:5173**
- API docs: **http://localhost:8010/docs**

### 5. Optional

In the panel: **Settings** → add API keys (Groq, Gemini, Claude, Telegram, Spotify), set default AI, toggle skills. Set your **location** in Chat (e.g. “Holon, Israel”) for time and weather.

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

3. **Frontend** (new terminal):

   ```powershell
   cd frontend
   npm install
   npm run dev
   ```

4. Open **http://localhost:5173** and **http://localhost:8010/docs**.

---

## Control script (Linux / macOS)

From the repo root, **`./asta.sh`** starts/stops both backend and frontend:

```bash
./asta.sh start     # start backend + frontend (frees ports first)
./asta.sh stop      # stop both
./asta.sh restart   # stop then start (e.g. after changing Telegram token)
./asta.sh status    # show if backend and frontend are running
```

**Settings → Restart backend** in the panel runs `./asta.sh restart`.

---

## Environment variables (`backend/.env`)

| Variable | Purpose |
|----------|--------|
| `GROQ_API_KEY` / `GEMINI_API_KEY` / `GOOGLE_AI_KEY` | Groq / Google AI |
| `ANTHROPIC_API_KEY` | Claude |
| `OPENAI_API_KEY` | OpenAI |
| `OLLAMA_BASE_URL` | e.g. `http://localhost:11434` (Ollama) |
| `TELEGRAM_BOT_TOKEN` | Telegram bot ([@BotFather](https://t.me/BotFather)) |
| `ASTA_ALLOWED_PATHS` | Comma-separated dirs for file access |
| `ASTA_CORS_ORIGINS` | Extra origins (e.g. LAN or Tailscale) |
| `ASTA_WHATSAPP_BRIDGE_URL` | e.g. `http://localhost:3001` (WhatsApp) |
| `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` | Or set in Settings → Spotify |
| `ASTA_BASE_URL` | Backend URL for Spotify OAuth redirect (optional) |

Many keys can also be set in **Settings → API keys** or **Settings → Spotify**; those are stored in the local DB and override `.env`. Restart the backend after changing the Telegram token.

**Audio notes:** No extra env; uses faster-whisper (local). **Reminders:** Stored in DB and re-loaded on backend startup.

---

## Run the API when it’s down

If the panel shows **“API off”**:

1. **Linux / macOS:** From repo root run `./asta.sh start` (or `./asta.sh restart`).
2. **Or manually:** `cd backend`, activate venv, then `uvicorn app.main:app --host 0.0.0.0 --port 8010`.
3. **Settings → Run the API** in the panel shows the exact commands.

---

## Troubleshooting

- **“Address already in use” (8010 or 5173)** — Run `./asta.sh restart` to free ports and start fresh. Or use another port, e.g. `uvicorn app.main:app --reload --port 8001` and update `VITE_API_URL` / `ASTA_API_URL` accordingly.
- **“Cannot reach Asta API” / “API off”** — Start the backend: `./asta.sh start` or run uvicorn as above. Panel talks to `http://localhost:8010/api` by default.
- **“No AI provider available”** — Add at least one of: `GROQ_API_KEY`, `GEMINI_API_KEY`, or run Ollama and set `OLLAMA_BASE_URL`.
- **Backend can’t find .env** — Backend reads **`backend/.env`** only. Run `cp .env.example backend/.env` from the repo root.
- **Lyrics / Spotify / Reminders** — Enable the skill in **Settings → Skills**. For Spotify, add Client ID and Secret in Settings → Spotify; for reminders, set location in Chat.
- **Reminders not firing** — Restart the backend once so pending reminders are re-loaded (`./asta.sh restart`).
- **Audio notes: “faster-whisper is not installed”** — Run `pip install -r requirements.txt` in the backend venv. First run may download the Whisper model (~140 MB).

---

## Easy install (planned)

Planned: a single command (e.g. `curl ... | sh` or `install.sh`) that pulls from GitHub and installs dependencies (Python venv, pip, Node/npm) so you can run `./asta.sh start` with minimal steps. See SPEC.md when available.
