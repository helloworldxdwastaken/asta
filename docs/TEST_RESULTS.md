# Asta — Test Results

Run the API smoke tests (with backend at http://localhost:8000):

```bash
./test_api.sh http://localhost:8000/api
```

## API tests (run 2026-02-10)

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
| GET /api/whatsapp/qr | ✅ 200 | qr/connected/error |
| POST /api/rag/learn | ✅ 200 | Uses Ollama first; if not running, falls back to OpenAI (then Google) embeddings. Needs at least one of: Ollama with `nomic-embed-text`, or OpenAI key, or Gemini/Google AI key. |

## Frontend

- `npm run build` (frontend): ✅ succeeds.
- Manual: open http://localhost:5173 (after `./asta.sh start` or `npm run dev` in frontend) and check Dashboard, Chat, Files, Learning, Audio notes, Skills, Settings.

## Environment-dependent behavior

- **RAG (learn/ask)**: Needs Ollama at `OLLAMA_BASE_URL` with `ollama pull nomic-embed-text`, and Chroma DB path writable. Otherwise POST /rag/learn can 500.
- **Chat**: Needs at least one AI provider (Groq, Gemini, Claude, or Ollama) configured; otherwise reply may be an error message.
- **Spotify play**: Needs Client ID/Secret and user to click "Connect Spotify" once.
- **Files**: Needs `ASTA_ALLOWED_PATHS` in backend/.env for non-empty list.
- **Telegram/WhatsApp**: Need bot token and WhatsApp bridge running for those channels.
