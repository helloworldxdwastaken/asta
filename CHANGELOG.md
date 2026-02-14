# Changelog

All notable changes to Asta are documented here.

## [1.3.1] - 2026-02-14

### Added

- **`asta doc` diagnostics command** — Added a safe diagnostic command (`./asta.sh doc`, alias `doctor`) to check environment/setup basics (Python, npm, backend venv, frontend deps, `.env`, workspace file) and include service/API health status.

### Changed

- **Control script docs/help updated** — Added `doc` command documentation in `README.md`, `docs/INSTALL.md`, and script help output.
- **Backend dependency manifest completeness** — Added missing direct dependencies used by runtime/tests: `ddgs`, `apscheduler`, `pillow`, and `pytest` in `backend/requirements.txt`.

---

## [1.3.0] - 2026-02-14

### Added

- **OpenClaw-style `process` tool companion** — Added background session management actions: `list`, `poll`, `log`, `write`, `kill`, `clear`, `remove`.
- **Exec background handoff** — `exec` now supports `background` and `yield_ms` so long-running commands can continue in background and be managed via `process`.
- **Process session registry** — In-memory running/finished session tracking with output tail/log buffering and TTL cleanup for finished sessions.

### Changed

- **Exec context/tool guidance** — System prompt now tells the model to use `process` after backgrounded exec responses (`status=running`, `session_id`).
- **Security parity status** — Asta now has foreground + background exec/process control, but still does not yet implement full OpenClaw exec-approval host/security policy orchestration.

---

## [1.2.1] - 2026-02-14

### Fixed

- **Reminder requests no longer fall into Apple Notes fallback text** — Added a reliability fallback for tool-capable providers: when reminder tool-calls are skipped, Asta now parses and schedules reminders directly from user intent.
- **Reminder parsing coverage** — Added support for common phrasing like `set an alarm for 10 am` and `set a reminder for tomorrow 11am`.
- **Exec fallback guard** — Legacy `[ASTA_EXEC: ...]` fallback is now executed only for clear exec intents (Apple Notes/Things), preventing unrelated prompts (shopping lists, reminders) from triggering exec-side error replies.
- **Shopping list intent routing** — Files skill eligibility now includes shopping/grocery list phrasing so list creation routes to workspace file-write flow more reliably.

### Added

- **Regression tests (parse/intent guards)** — Added focused tests for reminder parsing and exec-intent guard behavior.

---

## [1.2.0] - 2026-02-14

### Added

- **OpenClaw-style workspace skill selection** — Context now exposes only `<available_skills>` for workspace skills and a `read` tool, so the model selects one relevant skill and reads its `SKILL.md` on demand instead of injecting all skill bodies.
- **Structured tools for file workflows** — Added `list_directory`, `read_file`, `allow_path`, `delete_file`, and `delete_matching_files` tools. Supports desktop listing and screenshot cleanup flows with safer default trash behavior.
- **Structured reminders and cron tools** — Added `reminders` (`status/list/add/remove`) and `cron` (`status/list/add/update/remove`) action-based tools for one-time and recurring scheduling flows.
- **Skill install metadata in API/UI** — Workspace skill frontmatter now exposes install command/label + required bins. Skills page shows setup commands and auto-allowlist behavior for exec bins.

### Fixed

- **Desktop delete flow regression** — Requests like "check my desktop" then "delete screenshot files" no longer fall through to unrelated fallback text; the handler now routes through file tools and a grounded directory-summary fallback.
- **Unsafe exec bin extraction** — Required binaries are now parsed strictly from frontmatter metadata instead of regex scanning the entire `SKILL.md` body.
- **Context pollution from all enabled workspace skills** — Workspace skill bodies are no longer pre-injected into prompt context, reducing unrelated instruction bleed.

### Changed

- **Tool calls across providers** — Tool-call flow is now wired for OpenAI, Groq, OpenRouter, Claude, and Google paths, with provider-specific conversion/normalization and OpenRouter text-tag fallback.
- **Exec tool options** — `exec` now supports `timeout_sec` and safe `workdir` resolution for CLI-based skills (Apple Notes/Things) while preserving allowlist enforcement.
- **Default provider** — New users default to `openrouter` (Trinity Large remains usable as default if configured).

---

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

- **Exec: OpenClaw-style (tool only)** — Apple Notes and other exec-based skills now work like OpenClaw: the model calls an **exec tool** with a command (e.g. `memo notes`); the backend runs it and returns the result; the model replies from that output. No proactive run or pre-injected note content. Fallback: `[ASTA_EXEC: command][/ASTA_EXEC]` in the reply still works when the provider doesn't support tools. See `docs/SPEC.md` §4.2 and `docs/OPENCLAW-EXEC-NOTES.md`.
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
