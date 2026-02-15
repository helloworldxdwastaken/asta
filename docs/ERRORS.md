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
| **No AI provider found** | No API key set | Add at least one key in Settings → API keys: Groq, Gemini, Claude, OpenAI, OpenRouter, or run Ollama. |
| **invalid or expired API key** | Key wrong or expired | Update the key in Settings → API keys or `backend/.env`, then restart. |
| **Client error 404 for Ollama** | Ollama not running or wrong URL | Start Ollama (`ollama serve`) or set correct `OLLAMA_BASE_URL` in `backend/.env`. |
| **Image reply says it only sees `image/jpeg` / generic image placeholder** | Vision preprocessor/provider path is not configured (or no vision-capable key available). | Add at least one vision-capable key (OpenRouter, Claude, or OpenAI). Keep `ASTA_VISION_PREPROCESS=true` (default). If using OpenRouter vision, ensure `OPENROUTER_API_KEY` is set and optionally set `ASTA_VISION_OPENROUTER_MODEL`. |

---

## Skills & features

### Web search

| Symptom | Cause | Solution |
|---------|-------|----------|
| **AI says "I can't access the web"** | Search returned empty or failed | Asta uses ddgs (multi-backend). If DuckDuckGo blocks, it tries others. Ensure `ddgs` is installed: `pip install -r requirements.txt`. |
| **Search failed: [error message]** | API/network issue | Error is passed to the AI. Check backend logs. If persistent, DuckDuckGo/Bing may be rate-limiting. |
| **A normal question did not run web search** | Web search trigger is now stricter | Expected. Ask explicitly: “search the web for…”, “look up…”, “check the web…”, or include freshness intent like “latest”. |

### Reminders

| Symptom | Cause | Solution |
|---------|-------|----------|
| **Reminders not firing** | Pending reminders not loaded | Restart backend once: `./asta.sh restart`. Reminders are re-loaded on startup. |
| **Wrong timezone (e.g. 6pm instead of 8pm)** | Timezone lookup failed (now uses offline timezonefinder) | Set **Location** in workspace/USER.md (e.g. `**Location:** City, Country`) or tell Asta "I'm in City, Country". Restart backend after setting. |
| **Asta asks “Where are you?” for “wake me up at 7am”** | No location/timezone set | Expected. Absolute-time reminders require a timezone. Set location once, then retry. |
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
| **"I couldn't find X on Spotify"** for an artist | Old behavior only searched tracks | From 1.1.0, "Play [Artist]" searches artists and plays the artist context. Ensure backend is up to date. |

### Time & weather

| Symptom | Cause | Solution |
|---------|-------|----------|
| **I don't know your location** | No location saved | Add **Location** in workspace/USER.md or say "I'm in City, Country" in Chat. |
| **Always get UTC, not local time** | Location in USER.md not geocoding | Use **City, Country** or **City, CountryCode** (e.g. `Holon, Israel` or `Holon,IL`, `Chicago, USA`). Don’t wrap in italics only; we strip `_`. If it still fails, use full country name (e.g. `Israel`, `United States`). |

### Learning / RAG

| Symptom | Cause | Solution |
|---------|-------|----------|
| **RAG not available** / **Ollama not available** | RAG uses Ollama for embeddings; Ollama is not running or the model is missing | <code>curl -fsSL https://ollama.com/install.sh | sh</code> then <code>ollama pull nomic-embed-text</code>. Set <code>OLLAMA_BASE_URL</code> in <code>backend/.env</code> if Ollama is on another host. Then refresh the Learning page. |
| **RAG store failed: …** | ChromaDB or FTS DB could not be created | Check disk space and write permissions for <code>backend/chroma_db</code> and <code>backend/rag_fts.db</code>. Default paths can be overridden with <code>ASTA_CHROMA_PATH</code> and <code>ASTA_FTS_PATH</code> in <code>backend/.env</code>. |
| **Learned content but AI doesn’t use it** | RAG skill disabled or no relevant chunks | Enable **Learning (RAG)** in Settings → Skills. Ask questions that match the topic you learned. If you used a different topic name, refer to it (e.g. “What do you know about [topic]?”). |

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
| **Sent image in web chat but Asta cannot analyze it** | Web image upload path is not implemented yet. | Use Telegram photo input for vision turns. |

---

### Cron

| Symptom | Cause | Solution |
|---------|-------|----------|
| **Daily Auto-Update not created** | Auto-updater skill missing or backend not restarted | Ensure `workspace/skills/auto-updater-100` exists and restart backend. Or add a cron manually in the **Cron** tab or via `POST /api/cron`. |
| **Cron job not firing** | Scheduler not loaded or job disabled | Restart backend (cron jobs reload on startup). In Cron tab, ensure the job is listed and enabled. |

### Apple Notes / Exec (memo)

| Symptom | Cause | Solution |
|---------|-------|----------|
| **Asta said "I'll check your notes" but nothing happened** | The model must call the **exec tool** with the command (e.g. `memo notes`). If it only said it would check and didn't call the tool, you get no output. | Ask again: e.g. "List my Apple Notes" or "Run memo notes". Enable the **Apple Notes** skill in Settings → Skills (this adds `memo` to the exec allowlist). Install memo: `brew tap antoniorodr/memo && brew install antoniorodr/memo/memo`. |
| **memo command not found** | Backend runs with a minimal PATH (e.g. launched from IDE). | Restart the backend from a terminal where `memo` works, or ensure memo is in a standard path: `/opt/homebrew/bin`, `/usr/local/bin`, or `~/.local/bin` (Asta resolves these automatically). |
| **Command timed out / no response when checking notes** | On macOS, **permission is per process**. If you ran `memo notes` in Terminal and approved the dialog, that approval applies to **Terminal**. The Asta **backend** (Python) is a different process, so it may still need approval. | **Run the Asta backend from Terminal** (e.g. `./asta.sh start` or `cd backend && uvicorn app.main:app …`). Then ask Asta to check your notes. When the system dialog appears ("memo would like to access your notes"), click **Allow** — that grants access for the **process running the backend**. After that, Notes will work from Asta. |
| **Model never runs memo / says "I'll check" but no exec** | **Exec is implemented as a tool.** Only providers that support tools (Groq, OpenAI, OpenRouter) can call it. If your default provider is **Claude** or **Gemini**, the model never receives the exec tool, so it cannot run `memo notes`. | In Chat, switch the provider to **Groq**, **OpenAI**, or **OpenRouter** (Settings → API keys must be set). Then ask again for your notes. |
| **OpenRouter: no dialog, nothing happens when I ask for notes** | The model must **return** a tool call for Asta to run `memo`. Some OpenRouter models don't support tools; others (e.g. Trinity Large) do but may still sometimes reply with text only. If Asta never runs `memo`, no permission dialog appears. | Check backend log: look for `Exec allowlist: [...]` (confirm allowlist has memo) and `Provider openrouter returned tool_calls=...`. If `tool_calls=False`, see the next line. Try a model known for tools: openrouter.ai/models?supported_parameters=tools (e.g. **openai/gpt-4o-mini**). |
| **No permission dialog appeared** (backend run from Terminal) | The backend only runs `memo` when the model **calls the exec tool**. If the model doesn't call it (e.g. OpenRouter model without tool support), we never spawn `memo`, so no dialog. | Check backend log for `Exec tool called: command=...` — if that line never appears, the model didn't call the tool. Use a tool-capable provider/model (see row above). Ensure Apple Notes skill is enabled and allowlist has memo. |
| **Command timed out after 30s** (no dialog) | memo blocked (e.g. Keychain, slow disk). | Run `memo notes` once in Terminal and approve any dialog. For large note lists, use a search: e.g. "memo notes -s \"Eli\"". |
| **Exec is disabled / Command not allowed** | Exec allowlist empty or binary not in list | Enable the Apple Notes skill in Settings → Skills (auto-adds `memo`). Or set `ASTA_EXEC_ALLOWED_BINS=memo` in `backend/.env` and restart. |

---

## Logs & debugging

- **Backend logs:** `backend/backend.log` or `backend.log` in repo root (depends on where asta.sh runs from).
- **Frontend logs:** `frontend.log` or terminal where `npm run dev` runs.
- **API docs:** http://localhost:8010/docs for live endpoints and testing.
