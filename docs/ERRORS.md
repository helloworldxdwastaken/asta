# Asta — Common Errors & Solutions

Quick reference for errors you might see and how to fix them.

---

## Startup & install

| Error | Cause | Solution |
|-------|-------|----------|
| **Virtualenv missing** | No `.venv` in `backend/` | `cd backend && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt` |
| **ModuleNotFoundError** / **No module named 'X'** | Dependency not installed | `cd backend && source .venv/bin/activate && pip install -r requirements.txt` |
| **Port 8010 / 5173 already in use** | Another process holds the port | `./asta.sh restart` to free and restart. Or use another port and set `VITE_API_URL` / `ASTA_API_URL`. |
| **Directory not found: backend** | Wrong working directory | Run from the `asta/` repo root. |

---

## API & connection

| Error | Cause | Solution |
|-------|-------|----------|
| **API off** / **Cannot reach Asta API** | Backend not running | `./asta.sh start` or run uvicorn manually. |
| **CORS error** | Frontend origin not allowed | Add your origin to `ASTA_CORS_ORIGINS` in `backend/.env` (comma-separated). |

---

## AI providers

| Error | Cause | Solution |
|-------|-------|----------|
| **No AI provider found** | No API key set | Add at least one key in Settings → API keys: Groq, Gemini, Claude, or run Ollama. |
| **invalid or expired API key** | Key wrong or expired | Update the key in Settings → API keys or `backend/.env`, then restart. |
| **Client error 404 for Ollama** | Ollama not running or wrong URL | Start Ollama (`ollama serve`) or set correct `OLLAMA_BASE_URL` in `backend/.env`. |

---

## Skills & features

### Web search

| Symptom | Cause | Solution |
|---------|-------|----------|
| **AI says "I can't access the web"** | Search returned empty or failed | Asta uses ddgs (multi-backend). If DuckDuckGo blocks, it tries others. Ensure `ddgs` is installed: `pip install -r requirements.txt`. |
| **Search failed: [error message]** | API/network issue | Error is passed to the AI. Check backend logs. If persistent, DuckDuckGo/Bing may be rate-limiting. |

### Reminders

| Symptom | Cause | Solution |
|---------|-------|----------|
| **Reminders not firing** | Pending reminders not loaded | Restart backend once: `./asta.sh restart`. Reminders are re-loaded on startup. |
| **Wrong timezone (e.g. 6pm instead of 8pm)** | Timezone lookup failed (now uses offline timezonefinder) | Ensure location is set in Files → About you (User.md) or tell Asta "I'm in City, Country". Restart backend after setting. |
| **"I couldn't parse that reminder"** | Phrase not recognised | Use: "remind me in 5 min to X", "alarm in 5 min to X", "wake me up at 7am", "remind me at 6pm to X". |

### Lyrics

| Error | Cause | Solution |
|-------|-------|----------|
| **name 'lyrics_enabled' is not defined** | Old bug (fixed) | Update to latest code. |
| **No lyrics found** | Song/artist not in LRCLIB | Try different spelling or another source. |

### Spotify

| Symptom | Cause | Solution |
|---------|-------|----------|
| **Connect Spotify / reconnect** | Token expired or credentials changed | Settings → Spotify → Connect Spotify again. |
| **No devices available** | Spotify app not open on any device | Open Spotify on phone, computer, or speaker, then try again. |

### Time & weather

| Symptom | Cause | Solution |
|---------|-------|----------|
| **I don't know your location** | No location saved | Add in Files → About you (User.md) or say "I'm in City, Country" in Chat. |

---

## Files & data

| Error | Cause | Solution |
|-------|-------|----------|
| **No allowed paths configured** | `ASTA_ALLOWED_PATHS` empty | Add comma-separated directories in `backend/.env`, e.g. `ASTA_ALLOWED_PATHS=/home/you/docs,/home/you/notes`. |
| **Path not in allowed list** | File/folder outside allowed paths | Add the parent directory to `ASTA_ALLOWED_PATHS` or use a path inside it. |
| **User.md not found / empty** | File not created yet | It’s created on first backend start. Or run `asta install` which creates `data/User.md`. |

---

## Database & persistence

| Symptom | Cause | Solution |
|---------|-------|----------|
| **SQLite / DB errors** | Corrupt DB or permission issue | Check `backend/asta.db` exists and is writable. Back up and remove to start fresh if needed. |
| **ResourceWarning: Connection deleted before being closed** | Non-critical cleanup warning | Usually harmless. Can be ignored or fixed in future. |

---

## Audio notes

| Error | Cause | Solution |
|-------|-------|----------|
| **faster-whisper is not installed** | Missing dependency | `pip install -r requirements.txt` in backend venv. First run downloads the model (~140 MB). |

---

## WhatsApp / Telegram

| Symptom | Cause | Solution |
|---------|-------|----------|
| **Telegram handler error** | Bot token invalid or network issue | Check `TELEGRAM_BOT_TOKEN` in Settings or `backend/.env`. Get token from [@BotFather](https://t.me/BotFather). |
| **WhatsApp QR / bridge not connecting** | Bridge not running | Start `services/whatsapp` with `ASTA_API_URL=http://localhost:8010`. Set `ASTA_WHATSAPP_BRIDGE_URL` in `.env` if bridge runs elsewhere. |

---

## Logs & debugging

- **Backend logs:** `backend/backend.log` or `backend.log` in repo root (depends on where asta.sh runs from).
- **Frontend logs:** `frontend.log` or terminal where `npm run dev` runs.
- **API docs:** http://localhost:8010/docs for live endpoints and testing.
