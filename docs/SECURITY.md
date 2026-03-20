# Asta — Keeping secrets safe (no leaks to GitHub)

## Rule: never commit real secrets

All sensitive data lives in **one place**: `backend/.env`. That file is **gitignored**, so it is never pushed to GitHub.

- **Commit:** `.env.example` (this repo) — template only, no real keys or numbers.
- **Do not commit:** `backend/.env` — your real API keys, tokens, and private paths.

## Where to put your real config

1. **Create your env file (only on your machine):**
   ```bash
   cp .env.example backend/.env
   ```

   2. **Edit `backend/.env`** and add your real values. Examples (use your own):
   - `GROQ_API_KEY=gsk_...`
   - `GEMINI_API_KEY=...`
   - `OPENROUTER_API_KEY=...`
   - `TELEGRAM_BOT_TOKEN=123456:ABC...`
   - `ASTA_OWNER_PHONE_NUMBER=+15551234567` (if using Pingram voice calls)
   - `ASTA_ALLOWED_PATHS=/home/me/docs,/home/me/notes`
   - `SPOTIFY_CLIENT_ID=...` and `SPOTIFY_CLIENT_SECRET=...` (optional; can also be set in Settings → Spotify)
   - `PEXELS_API_KEY=...` (YouTube pipeline footage sourcing)
   - `PIXABAY_API_KEY=...` (YouTube pipeline footage sourcing)
   - `YOUTUBE_API_KEY=...` (YouTube Data API v3 for trend discovery + upload)

   **Alternatively,** you can store API keys in the panel under **Settings**. They are saved in `backend/asta.db`. The backend reads stored keys first, then falls back to `.env`. Do not commit `asta.db` if it contains keys.

3. **Never add these to the repo:**
   - API keys (Groq, Gemini, Anthropic, OpenAI, OpenRouter, Spotify, Pexels, Pixabay, YouTube)
   - Telegram bot token
   - Phone numbers (e.g., owner reminder/call target numbers)
   - Paths that include your username or sensitive dirs (use generic docs in `.env.example`)
   - The file `backend/asta.db` (it may contain stored API keys and chat/reminder data)
   - `workspace/youtube/youtube_tokens.json` — OAuth tokens from YouTube Data API auth flow
   - `workspace/youtube/client_secret.json` — Google OAuth client secret for YouTube upload

## Authentication

Asta supports **multi-user JWT authentication**. When users exist in the database, all API endpoints require a valid JWT token (except `/api/auth/login` and `/api/auth/register`).

- **JWT secret:** Auto-generated and stored in `backend/.env` as `ASTA_JWT_SECRET`. Rotating this invalidates all existing tokens.
- **Password hashing:** bcrypt with random salt.
- **Token expiry:** 30 days.
- **Role-based access:** Admin users have full access. Regular users are restricted to chat with safe tools only.
- **Backward compatibility:** When no users exist in the DB, Asta falls back to legacy Bearer token auth (single-user mode).

## What is gitignored (won’t be pushed)

- `backend/.env` — env-based secrets (including `ASTA_JWT_SECRET`)
- `backend/asta.db` — DB with chat, reminders, stored API keys (Settings), Spotify tokens, **user accounts and password hashes**
- `backend/chroma_db/` — RAG vectors
- `workspace/users/` — per-user memory files
- `workspace/youtube/youtube_tokens.json` — YouTube OAuth access/refresh tokens
- `workspace/youtube/client_secret.json` — Google OAuth client secret for YouTube upload
- Any file named `.env`, `.env.local`, or under `secrets/`

See the project root **`.gitignore`** for the full list.

## Before you push (verify nothing sensitive is committed)

Run this — it should list **no** files; if it lists anything, unstage and add to `.gitignore`:

```bash
git status
git diff --cached --name-only | grep -E '\.env$|\.env\.|secrets/|\.db$|credentials|token\.json' || true
```

- You must **not** see `backend/.env`, any `.env`, or `backend/asta.db` in `git status`.
- If any of those appear, run: `git restore --staged <file>` then add the path to `.gitignore` if needed.

**If you ever committed `.env` by mistake:**
   - Run `git rm --cached backend/.env` (or the path you committed), commit that change, and add the path to `.gitignore`. Then **rotate all keys and tokens** that were in that file (they are considered exposed).

## Testing locally

- Use `backend/.env` with real keys and numbers for local and staging.
- For CI (e.g. GitHub Actions), use repository secrets / env vars in the workflow only, never in the code or in a committed file.
