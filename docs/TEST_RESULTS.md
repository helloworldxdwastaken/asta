# Asta — Test Results

This file records the latest documented smoke-test run. Re-run before release:

```bash
./test_api.sh http://localhost:8010/api
```

## API tests (documented run: 2026-02-10)

| Endpoint | Result | Notes |
|----------|--------|--------|
| GET /api/health | ✅ 200 | `{"status":"ok","app":"Asta"}` |
| GET /api/status | ✅ 200 | apis, integrations, skills |
| GET /api/providers | ✅ 200 | list of AI providers |
| GET /api/settings/default-ai | ✅ 200 | default provider |
| GET /api/settings/keys | ✅ 200 | which keys are set |
| GET /api/settings/models | ✅ 200 | model per provider |
| GET /api/settings/skills | ✅ 200 | skills with enabled/available |
| GET /api/files/list | ✅ 200 | roots/entries (empty if no ASTA_ALLOWED_PATHS) |
| GET /api/drive/status | ✅ 200 | connected/summary |
| GET /api/drive/list | ✅ 200 | files when connected |
| GET /api/rag/learned | ✅ 200 | has_learned, topics |
| GET /api/spotify/status | ✅ 200 | connected (OAuth) |
| GET /api/spotify/setup | ✅ 200 | connect_url, steps |
| POST /api/chat | ✅ 200 | reply, conversation_id, provider |
| GET /api/notifications | ✅ 200 | reminders list |
| POST /api/rag/learn | ✅ 200 | Uses Ollama embeddings (`nomic-embed-text`). Requires Ollama to be running and reachable. |

## Frontend

- `npm run build` (frontend): ✅ succeeds.
- Manual: open http://localhost:5173 (after `./asta.sh start` or `npm run dev` in frontend) and check Dashboard, Chat, Files, Learning, Audio notes, Skills, Settings.

## Environment-dependent behavior

- **RAG (learn/ask)**: Needs Ollama at `OLLAMA_BASE_URL` with `ollama pull nomic-embed-text`, and Chroma DB path writable. Otherwise POST /rag/learn can 500.
- **Chat**: Needs at least one AI provider (Groq, Gemini, Claude, or Ollama) configured; otherwise reply may be an error message.
- **Spotify play**: Needs Client ID/Secret and user to click "Connect Spotify" once.
- **Files**: Needs `ASTA_ALLOWED_PATHS` in backend/.env for non-empty list.
- **Telegram**: Needs a valid `TELEGRAM_BOT_TOKEN` for bot channel features.

## Backend regression tests (2026-02-24)

Command run:

```bash
cd backend
./.venv/bin/pytest \
  tests/test_image_gen_tool.py \
  tests/test_image_generation_guardrail.py \
  tests/test_telegram_markdown_media.py -q
```

Result:

- `13 passed`
- `1 warning` (pydantic deprecation warning, non-blocking)
