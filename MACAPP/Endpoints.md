# Asta API endpoints (for Mac app)

All routes are under base URL `http://localhost:8010` (or `ASTA_BASE_URL`). Prefix **/api** where noted.

## Root & health

| Method | Path        | Description        |
|--------|-------------|--------------------|
| GET    | /           | App name, version, docs |
| GET    | /health     | Health check       |
| GET    | /api/health | Same               |

## Chat

| Method | Path              | Description                    |
|--------|-------------------|--------------------------------|
| GET    | /api/chat/messages | Recent messages (query: `conversation_id`, `user_id`, `limit`) |
| POST   | /api/chat         | Send message (JSON: `text`, `provider`, `user_id`, `conversation_id`, `mood`) |
| POST   | /api/chat/stream  | Streaming chat (SSE)           |

## Settings (all under /api)

| Method | Path                               | Description              |
|--------|------------------------------------|--------------------------|
| GET    | /api/status                        | Backend status          |
| GET    | /api/settings/default-ai           | Default AI provider      |
| PUT    | /api/settings/default-ai           | Set default AI           |
| GET    | /api/settings/thinking             | Thinking level           |
| PUT    | /api/settings/thinking             | Set thinking             |
| GET    | /api/settings/reasoning            | Reasoning mode           |
| PUT    | /api/settings/reasoning            | Set reasoning            |
| GET    | /api/settings/vision               | Vision preprocess/model  |
| PUT    | /api/settings/vision               | Set vision               |
| GET    | /api/settings/provider-flow        | Provider enable/order    |
| PUT    | /api/settings/provider-flow/provider-enabled | Toggle provider |
| GET    | /api/settings/fallback             | Fallback config          |
| PUT    | /api/settings/fallback             | Set fallback             |
| GET    | /api/settings/models               | Current models           |
| PUT    | /api/settings/models               | Set models               |
| GET    | /api/settings/available-models     | Available models         |
| GET    | /api/settings/keys                 | Keys (masked)            |
| PUT    | /api/settings/keys                 | Update keys              |
| GET    | /api/settings/skills               | Skills list              |
| PUT    | /api/settings/skills               | Update skills            |
| GET    | /api/settings/memory-health        | RAG/memory health        |
| GET    | /api/settings/security-audit       | Security audit           |
| GET    | /api/settings/server-status        | Server status            |
| GET    | /api/settings/check-update         | Update check             |
| POST   | /api/settings/update               | Trigger update           |
| GET    | /api/settings/pingram              | Pingram/Voice config     |
| POST   | /api/settings/pingram              | Update Pingram           |
| POST   | /api/settings/pingram/test-call    | Test voice call          |
| GET    | /api/settings/telegram/username    | Telegram bot username    |
| POST   | /api/settings/telegram/username    | Set Telegram username    |
| GET    | /api/notifications                 | Notifications            |
| DELETE | /api/notifications/{id}            | Delete notification      |

## Files

| Method | Path                   | Description        |
|--------|------------------------|--------------------|
| GET    | /api/files/list        | List path (query)  |
| GET    | /api/files/read        | Read file (query)  |
| PUT    | /api/files/write       | Write file         |
| GET    | /api/files/allowed-paths | Allowed paths   |
| POST   | /api/files/allow-path  | Allow path         |
| PUT    | /api/files/allow-path  | Allow path         |

## Cron

| Method | Path                      | Description     |
|--------|---------------------------|-----------------|
| GET    | /api/cron                 | List jobs       |
| POST   | /api/cron                 | Create job      |
| PUT    | /api/cron/{job_id}        | Update job      |
| DELETE | /api/cron/{job_id}        | Delete job      |

## RAG / learning

| Method | Path                    | Description     |
|--------|-------------------------|-----------------|
| GET    | /api/rag/status         | RAG status      |
| GET    | /api/rag/learned        | Learned topics  |
| POST   | /api/rag/learn          | Start learning  |
| POST   | /api/rag/ask            | Ask RAG         |
| GET    | /api/rag/topic/{topic}  | Topic info      |
| PUT    | /api/rag/topic/{topic}  | Update topic    |
| DELETE | /api/rag/topic/{topic}  | Delete topic    |

## Other

| Method | Path                 | Description      |
|--------|----------------------|------------------|
| GET    | /api/providers       | AI providers     |
| POST   | /api/restart         | Restart backend  |
| GET    | /api/spotify/setup   | Spotify setup    |
| GET    | /api/spotify/devices | Spotify devices  |
| POST   | /api/spotify/play    | Spotify play     |
| GET    | /api/audio/status/{job_id} | Audio job status |
| POST   | /api/audio/process   | Process audio    |
| GET    | /api/drive/status    | Drive status     |
| GET    | /api/drive/list     | Drive list       |
