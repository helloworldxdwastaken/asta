# Asta — Keeping secrets safe (no leaks to GitHub)

## Rule: never commit real secrets

All sensitive data lives in **one place**: `backend/.env`. That file is **gitignored**, so it is never pushed to GitHub.

- **Commit:** `.env.example` (this repo) — template only, no real keys or numbers.
- **Do not commit:** `backend/.env` — your real API keys, tokens, paths, WhatsApp bridge URL.

## Where to put your real config

**If you had an old `.env` with `CLAWD_*` variables:** rename them to `ASTA_*` (e.g. `CLAWD_ALLOWED_PATHS` → `ASTA_ALLOWED_PATHS`).

1. **Create your env file (only on your machine):**
   ```bash
   cp .env.example backend/.env
   ```

2. **Edit `backend/.env`** and add your real values. Examples (use your own):
   - `GROQ_API_KEY=gsk_...`
   - `GEMINI_API_KEY=...`
   - `TELEGRAM_BOT_TOKEN=123456:ABC...`
   - `ASTA_WHATSAPP_BRIDGE_URL=http://localhost:3001`
   - `ASTA_ALLOWED_PATHS=/home/me/docs,/home/me/notes`
   - `SPOTIFY_CLIENT_ID=...` and `SPOTIFY_CLIENT_SECRET=...` (optional; can also be set in Settings → Spotify)

   **Alternatively,** you can store API keys in the panel under **Settings**. They are saved in `backend/asta.db`. The backend reads stored keys first, then falls back to `.env`. Do not commit `asta.db` if it contains keys.

3. **Never add these to the repo:**
   - API keys (Groq, Gemini, Anthropic, OpenAI, Spotify)
   - Telegram bot token
   - WhatsApp numbers (they only appear in your local DB if you use reminders)
   - Paths that include your username or sensitive dirs (use generic docs in `.env.example`)
   - The file `backend/asta.db` (it may contain stored API keys and chat/reminder data)

## What is gitignored (won’t be pushed)

- `backend/.env` — env-based secrets
- `backend/asta.db` — DB with chat, reminders, stored API keys (Settings), Spotify tokens
- `backend/chroma_db/` — RAG vectors
- `services/whatsapp/.wweb_auth/` — WhatsApp session (never commit)
- Any file named `.env`, `.env.local`, or under `secrets/`

See the project root **`.gitignore`** for the full list.

## Before you push (verify nothing sensitive is committed)

Run this — it should list **no** files; if it lists anything, unstage and add to `.gitignore`:

```bash
git status
git diff --cached --name-only | grep -E '\.env$|\.env\.|secrets/|\.db$|\.wweb_auth|credentials|token\.json' || true
```

- You must **not** see `backend/.env`, any `.env`, `backend/asta.db`, or `services/whatsapp/.wweb_auth` in `git status`.
- If any of those appear, run: `git restore --staged <file>` then add the path to `.gitignore` if needed.

**If you ever committed `.env` by mistake:**
   - Run `git rm --cached backend/.env` (or the path you committed), commit that change, and add the path to `.gitignore`. Then **rotate all keys and tokens** that were in that file (they are considered exposed).

## Testing locally

- Use `backend/.env` with real keys and numbers for local and staging.
- For CI (e.g. GitHub Actions), use repository secrets / env vars in the workflow only, never in the code or in a committed file.
