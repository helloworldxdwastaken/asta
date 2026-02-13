# Changelog

All notable changes to Asta are documented here.

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
