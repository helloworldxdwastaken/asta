# Asta

One place to talk to AI, automate tasks, and stay in control: **web panel**, **Telegram**, and **WhatsApp**. One user, one context.

**AI:** Groq, Google Gemini, Claude, Ollama — set your default in Settings.  
**Skills:** Time & weather, web search, lyrics, Spotify (search + play on your devices), reminders (“wake me up at 7am”), audio notes (upload/voice → transcript + meeting notes), and **learn about X for Y minutes** (background learning + notify when done).  
**Data:** Chat history, files (allowed paths), Google Drive (stub), and learned knowledge (RAG with Ollama + Chroma). No Docker — **native install** only.

---

## Quick start

**1. Clone and config**

```bash
git clone https://github.com/helloworldxdwastaken/asta.git
cd asta
cp .env.example backend/.env
# Edit backend/.env with API keys (optional at first)
```

**2. Backend + frontend (Linux / macOS)**

```bash
./asta.sh start
```

Then open **http://localhost:5173** (panel) and **http://localhost:8000** (API docs).

**3. Or run by hand**

```bash
# Backend
cd backend && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Frontend (other terminal)
cd frontend && npm install && npm run dev
```

Panel: **http://localhost:5173**. If it says “API off”, start the backend (or use **Settings → Run the API** in the panel).

---

## Control script (`asta.sh`)

From the repo root (Linux / macOS):

| Command | What it does |
|--------|----------------|
| `./asta.sh start` | Start backend + frontend (frees ports 8000 and 5173 first) |
| `./asta.sh stop` | Stop both |
| `./asta.sh restart` | Stop, then start both (e.g. after changing Telegram token) |
| `./asta.sh status` | Show if backend and frontend are running |

---

## What’s in the panel

- **Dashboard** — Overview and quick links  
- **Chat** — Talk to Asta; skills (search, time, weather, lyrics, Spotify, reminders, audio notes, learning) run when relevant  
- **Files** — Browse allowed paths (set `ASTA_ALLOWED_PATHS` in `backend/.env`)  
- **Drive** — Google Drive (OAuth stub)  
- **Learning** — RAG: “learn about X for 30 min”, ask later; semantic search so answers use only relevant learned bits  
- **Audio notes** — Upload or paste a link; transcribe (local faster-whisper) and get meeting notes or summary; saved for “last meeting?”  
- **Settings** — API keys (Groq, Gemini, Claude, Telegram, Spotify), default AI, skill toggles, “Run the API”, “Restart backend”  
- **Skills** — Enable/disable time, weather, web search, lyrics, Spotify, reminders, audio notes, learning  

**Telegram:** Set `TELEGRAM_BOT_TOKEN` in `backend/.env` or Settings; same user as the panel.  
**WhatsApp:** Run `services/whatsapp` with `ASTA_API_URL=http://localhost:8000`; scan QR in Settings.

---

## Docs

- **`docs/INSTALL.md`** — Full native install (macOS, Linux, Windows), env vars, troubleshooting.  
- **`docs/SPEC.md`** — Product spec and where to add features.  
- **`docs/SECURITY.md`** — Keep secrets in `backend/.env` only; never commit them.

---

## Easy install (planned)

A single command that clones (or pulls) from GitHub and installs dependencies (venv, pip, npm) so you can run `./asta.sh start` — coming later.

---

## Project layout

```
asta/
├── backend/           # FastAPI — backend/.env, API keys also in Settings (DB)
├── frontend/          # React + Vite (panel)
├── services/whatsapp/ # WhatsApp bridge (Node)
├── docs/              # INSTALL.md, SPEC.md, SECURITY.md
├── asta.sh            # Start/stop/restart backend + frontend
├── .env.example       # Copy to backend/.env
└── README.md
```

---

## License

Use and modify as you like.
