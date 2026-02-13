# Changelog

All notable changes to Asta are documented here.

## [1.1.0] - 2026-02-14

### Added

- **Cron tab** — New sidebar page to list and remove scheduled cron jobs. Shows name, schedule (5-field cron), timezone, message, created date, and Remove button. API: `PUT /api/cron/{id}` to update schedule/timezone/message.
- **Auto-updater cron** — When the auto-updater skill is present (`workspace/skills/auto-updater-100`), backend creates a "Daily Auto-Update" cron job on startup (4 AM daily) if none exists. Settings → Auto-updater lets you change schedule and timezone.
- **Dashboard: Schedule & Capabilities** — Schedule card shows count of scheduled cron jobs with link to Cron tab. Capabilities card shows total active skills count (no full list) with link to Skills.
- **Dashboard: The Eyes next to Brain & Body** — Vision panel moved to top row (Brain | Body | Eyes). Four-column layout; row 2: Channels, Tasks, Schedule, Capabilities.
- **Dashboard: CPU model** — Body panel shows CPU model name and core count (e.g. "Apple M2 · 8 cores") from server status. Backend `GET /api/settings/server-status` now returns `cpu_model` and `cpu_count`.
- **Ollama models in status** — Backend `GET /api/settings/available-models` returns list of Ollama local models for the dashboard.

### Fixed

- **Local time from USER.md** — Location value was read with markdown italics (e.g. `_Holon,IL_`). Strip underscores when parsing; normalize country codes (e.g. "Holon,IL" → "Holon, Israel", "Chicago, USA" → "Chicago, United States") before geocoding so "What time is it?" returns user's local time.
- **Spotify: Play artist** — "Play Bob Dylan" now works: when no track matches, Asta searches artists and starts playback with `context_uri=spotify:artist:...` so you hear the artist’s content instead of "I couldn't find...".
- **Dashboard: Ollama model display** — Only show an Ollama model that is actually installed. If the configured default (e.g. llama3.2) is not in `ollama list`, show the first available model instead of the missing one.
- **Dashboard: centered layout** — Main content uses full width (main-inner `max-width: 100%`); dashboard container centers with `max-width: 1600px` and equal padding so the panel no longer looks shifted right.

### Changed

- **Dashboard layout** — Wider (1600px max), more padding and gap (2rem). Brain no longer shows provider logos; all providers use the same style (label + model line; Ollama adds comma-separated list of installed models).
- **Cron API** — `PUT /api/cron/{job_id}` with body `{ cron_expr?, tz?, message? }` updates a job and reschedules it.
- **Requirements** — No change; Python 3.12 or 3.13, `pydantic<2.12`. See `backend/requirements.txt` and `docs/INSTALL.md`.

---

## [1.0.0] - 2026-02-13

### Added

- **Claw-style exec tool** — Asta can run allowlisted shell commands (e.g. `memo`, `things`) when the model outputs `[ASTA_EXEC: command][/ASTA_EXEC]`. Commands run on the server; output is fed back to the model so it can answer (e.g. "check my Apple Notes about Eli"). Configure via `ASTA_EXEC_ALLOWED_BINS=memo,things` in `backend/.env`.
- **Claw-style cron** — Recurring jobs with 5-field cron expressions. The model can schedule cron via `[ASTA_CRON_ADD: name|cron_expr|tz|message][/ASTA_CRON_ADD]` and remove via `[ASTA_CRON_REMOVE: name][/ASTA_CRON_REMOVE]`. When a cron fires, the message is sent through the handler and the reply is delivered to the user (Telegram/WhatsApp). API: `GET/POST/DELETE /api/cron`. Skills (e.g. auto-updater) can rely on cron.
- **Workspace & OpenClaw-style skills** — Default `workspace/` folder (auto-created). Skills loaded from `workspace/skills/*/SKILL.md` (name + description). Bundled workspace skills: notes, apple-notes, things-mac, weather, skill-creator, auto-updater-100. User context from `workspace/USER.md` only.
- **Mac skills from OpenClaw** — `apple-notes` (memo CLI for Apple Notes) and `things-mac` (things CLI for Things 3), marked Mac-only in descriptions.
- **Notes skill** — Save quick notes and lists to `workspace/notes/` via the same file-creation convention as the files skill.
- **Skills page redesign** — 3-column grid of skill cards with Connect / Configure / Ready pills. Backend returns `action_hint` for skills that need setup (e.g. "Connect", "Configure paths", "Set API key") with link to Settings.
- **Settings** — Provider cards with logos, "Get your API key" links, editable model field, Save per card. Telegram moved to Channels; API keys section is AI providers + optional extras (e.g. Giphy).
- **Dashboard** — Brain shows only connected AI providers. Clearer section icons and empty states.
- **Chat** — Web vs Telegram tabs, message history from DB, modern layout (bubbles, typing indicator). Channel badge and Ctrl+Enter to send.
- **Telegram sync** — User message is persisted early so the web UI shows it even when the handler or provider fails. All assistant replies (including errors) are saved so the Telegram preview matches what the user saw. On handler exception, user + error are persisted so the web UI stays in sync.
- **File creation** — Handler parses `[ASTA_WRITE_FILE: path]...[/ASTA_WRITE_FILE]` and creates files under allowed paths / workspace. Files skill instructions tell the model to use this for "save to file", "create a shopping list", etc.
- **Cron API** — `GET /api/cron`, `POST /api/cron`, `DELETE /api/cron/{id}` for listing, adding, and removing cron jobs.
- **Docs** — `docs/WORKSPACE.md` for workspace, USER.md, and skills. `.env.example` documents `ASTA_EXEC_ALLOWED_BINS` and `ASTA_WORKSPACE_DIR`.

### Fixed

- **Chat router** — Added missing `from pydantic import BaseModel` in `backend/app/routers/chat.py` (NameError on startup).
- **Handler `re` scope** — Removed redundant `import re` inside a block in `handler.py` that caused "cannot access local variable 're'" when the block was skipped.

### Changed

- **Reminders** — Unchanged; one-off reminders (APScheduler + DB) still work. Cron adds recurring jobs alongside them.
- **Version** — Bumped to 1.0.0 for this release.

---

Format based on [Keep a Changelog](https://keepachangelog.com/).
