# Push to GitHub (no credentials)

The repo is set up so **secrets are never committed**. Safe to push.

## What’s ignored (see `.gitignore`)

- `.env`, `backend/.env`, any `*.env.*` (except `.env.example`)
- `backend/asta.db`, `backend/chroma_db/`
- `*.key`, `*.pem`, `credentials.json`, `token.json`, `secrets/`
- `*.log`, `.asta.pid`, `.asta-frontend.pid`
- `node_modules/`, `.venv/`

Only **`.env.example`** (placeholders, no real keys) is committed.

## Push steps

1. **Create a new repo on GitHub** (empty, no README).

2. **Add the remote and push** (replace `YOUR_USER` and `YOUR_REPO`):

   ```bash
   cd /path/to/Clawd
   git remote add origin https://github.com/YOUR_USER/YOUR_REPO.git
   git push -u origin main
   ```

   Or with SSH:

   ```bash
   git remote add origin git@github.com:YOUR_USER/YOUR_REPO.git
   git push -u origin main
   ```

3. **If you already added a remote** with the wrong URL:

   ```bash
   git remote set-url origin https://github.com/YOUR_USER/YOUR_REPO.git
   git push -u origin main
   ```

Done. Your API keys and tokens stay in `.env` / Settings only and are never pushed.
