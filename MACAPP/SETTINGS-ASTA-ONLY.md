# Settings: Asta only (do not use OpenClaw config)

OpenClaw’s Mac app has a **lot** of configuration (gateway, agents, tools, channels, nodes, exec approvals, etc.). Asta is different: it has a single backend and a **smaller, fixed set** of settings exposed via REST.

**Rule:** Any Settings UI in the Asta Mac app (tray, dashboard, or standalone) must be driven **only by Asta’s API** below. Do **not** copy OpenClaw’s config schema, gateway methods, or UI labels; they don’t apply to Asta.

## What to use (Asta API)

These are the **only** configuration surfaces the Mac app should expose. All via `GET/PUT` (or `POST` where noted) to `baseURL + path`.

| What user sees (example label) | Asta endpoint | Notes |
|---------------------------------|---------------|--------|
| Default AI provider | `GET/PUT /api/settings/default-ai` | `provider`: claude, ollama, openrouter, etc. |
| Thinking level | `GET/PUT /api/settings/thinking` | `level`: off, minimal, low, medium, high, xhigh |
| Reasoning visibility | `GET/PUT /api/settings/reasoning` | `mode`: off, on, stream |
| Final mode (strict) | `GET/PUT /api/settings/final-mode` | |
| Vision (preprocess + model) | `GET/PUT /api/settings/vision` | Provider order, OpenRouter model for vision |
| Provider on/off + order | `GET /api/settings/provider-flow`, `PUT /api/settings/provider-flow/provider-enabled` | Claude, Ollama, OpenRouter enable + order |
| Fallback | `GET/PUT /api/settings/fallback` | |
| Model per provider | `GET/PUT /api/settings/models`, `GET /api/settings/available-models` | |
| API keys | `GET/PUT /api/settings/keys` | Masked in GET; PUT to update |
| Skills | `GET/PUT /api/settings/skills` | Enable/disable workspace skills |
| Telegram username | `GET/POST /api/settings/telegram/username` | |
| Voice (Pingram) | `GET/POST /api/settings/pingram`, `POST .../pingram/test-call` | |
| Notifications | `GET /api/notifications`, `DELETE /api/notifications/{id}` | |
| Cron jobs | `GET/POST/PUT/DELETE /api/cron` | List, add, update, remove |
| Status / health | `GET /api/status`, `GET /api/health` | Dashboard status line |

## What not to use

- **OpenClaw gateway methods** (e.g. `config.get`, `config.patch`, `agents.files.list`, `exec.approvals.node.get`) — Asta has no gateway; it has one backend with the routes above.
- **OpenClaw-specific UI** (agents, channels config, node pairing, exec approval allowlists per node, etc.) — either not in Asta or mapped differently (e.g. exec allowlist is in Asta backend/env and Telegram `/allow`).
- **OpenClaw schema** (tools.profile, tools.allow/deny, agents.*, etc.) — ignore for the Mac app; use only the Asta endpoints in this repo.

## Tray / dashboard

You can keep a **tray + dashboard** UX similar to OpenClaw (tap system tray → open a panel). The **content** of that panel must be:

- **Status:** from `GET /api/status` and `GET /api/health`.
- **Quick actions / links:** e.g. open Asta web panel, open docs.
- **Settings:** only the items in the table above, each bound to the corresponding Asta API call. No OpenClaw-only options.

So: **yes, configuration parameters in Settings are adapted to Asta** — they are exactly the Asta API settings listed here. The client in `Sources/AstaAPIClient` and `Endpoints.md` already target these; any future Settings UI must use only these endpoints and labels.
