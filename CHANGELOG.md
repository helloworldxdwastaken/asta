# Changelog

All notable changes to Asta are documented here.

## [Unreleased]

### Added

- **Thinking + reasoning controls** — Added persisted per-user AI controls:
  - `thinking_level`: `off | low | medium | high`
  - `reasoning_mode`: `off | on | stream`
  Exposed in Settings API/UI and wired into handler/provider flow.
- **Telegram controls for reasoning/thinking** — Added bot commands and inline pickers:
  - `/thinking` (and `/thinking <level>`)
  - `/reasoning` (and `/reasoning <mode>`)
  Registered in Telegram bot menu.
- **Subagent command UX (single-user)** — Added deterministic `/subagents` command handling (`list/spawn/info/send/stop/help`) in core handler, plus Telegram `/subagents` command registration/menu entry.
- **Subagent auto-spawn policy (single-user)** — Added conservative deterministic auto-spawn for explicit background requests and clearly complex long multi-step prompts, with env toggle `ASTA_SUBAGENTS_AUTO_SPAWN`.
- **Subagent send wait mode** — Added wait support for follow-up messages (`sessions_send.timeoutSeconds` and `/subagents send ... --wait <seconds>`), returning immediate reply/timeout status when requested.
- **Hybrid vision preprocessor flow** — Added image preprocessing pipeline: analyze image with a vision provider first (default order `openrouter,claude,openai`), then pass structured vision analysis to the main selected provider for final response/tool actions.
- **Multimodal provider payload support** — Added native image payload formatting for Claude and OpenAI provider adapters.

### Changed

- **Tool-trace UX by channel** — Telegram replies no longer append the `Tools used: ...` footer even when tracing is enabled (Telegram already shows proactive skill-status pings). Web trace behavior remains available.
- **Tool-trace defaults** — Default trace channels now target web (`ASTA_TOOL_TRACE_CHANNELS=web`).
- **Docs alignment pass** — Updated README + INSTALL + SPEC + WORKSPACE to reflect implemented behavior and new commands/settings.
- **Reminder scheduling internals aligned to cron path** — One-shot reminders now use the cron scheduler path (`@at <ISO-UTC>` entries) for execution, with startup migration of legacy pending reminder rows.
- **Subagent run summaries** — Improved `/subagents list` and `/subagents info` output with richer status/meta fields (model/thinking/timestamps).
- **Vision provider config surface** — Added env settings for vision preprocessing behavior and provider/model selection:
  - `ASTA_VISION_PREPROCESS`
  - `ASTA_VISION_PROVIDER_ORDER`
  - `ASTA_VISION_OPENROUTER_MODEL`

### Fixed

- **Stale changelog reference** — Removed reference to deleted `docs/OPENCLAW-EXEC-NOTES.md` and pointed to current spec documentation.
- **Reminder remove/list consistency** — Reminder delete/list/status flows now operate on the same one-shot scheduler source, reducing cases where a removed reminder still appeared pending.

---

## [1.3.7] - 2026-02-15

### Fixed

- **Files fallback reliability across providers** — Tool-required file-check guardrails now treat `ollama` as tool-capable, so empty/non-tool replies no longer fall through to generic “didn't get a reply” behavior on desktop/file checks.
- **Natural file-check phrasing support** — Deterministic files fallback now recognizes prompts like `any screenshots on my desktop?` and matches simple singular/plural variants (`screenshot`/`screenshots`) for more accurate results.
- **Cross-provider behavior check** — Verified desktop file-check fallback behavior for `openrouter` and `claude` request paths so connection/tool-call misses still resolve to factual file-tool responses when intent is clear.

---

## [1.3.6] - 2026-02-15

### Added

- **Subagent concurrency control** — Added `ASTA_SUBAGENTS_MAX_CONCURRENT` (default `3`) and enforced spawn guard so `sessions_spawn` returns `busy` when the cap is reached.
- **Per-spawn model/thinking overrides** — `sessions_spawn` now accepts:
  - `model` (provider model override for that child run)
  - `thinking` (`off|low|medium|high`) override for that child run
  Overrides are persisted on the run and reused by `sessions_send`.
- **Auto-archive timer for keep-mode runs** — Added timed cleanup of child sessions for `cleanup=keep` runs. Archive marks `archived_at` and removes child conversation messages while preserving run metadata.
- **Subagent metadata persistence** — `subagent_runs` now stores `model_override`, `thinking_override`, `run_timeout_seconds`, and `archived_at`.
- **Recovery enhancement** — Startup recovery now also restores archive timers for completed non-archived keep-mode runs.

### Fixed

- **Subagent runtime stability** — Corrected orchestration runtime edge cases and validated with expanded tests.

### Changed

- **Orchestration tests expanded** — Added tests for concurrency cap, per-spawn overrides, and auto-archive behavior.

---

## [1.3.5] - 2026-02-14

### Added

- **Single-user subagent orchestration (OpenClaw-style)** — Added tool support for:
  - `agents_list`
  - `sessions_spawn` (non-blocking background spawn)
  - `sessions_list`
  - `sessions_history`
  - `sessions_send`
  - `sessions_stop`
- **Subagent runtime registry** — Added persisted run lifecycle tracking in `subagent_runs` (status/result/error/timestamps, parent/child conversation mapping).
- **Subagent announce flow** — Completed/failed/timed-out subagent runs now post an assistant update back to the parent conversation and notify Telegram/WhatsApp when applicable.
- **Startup recovery for unfinished runs** — Backend startup now marks previously running subagent runs as `interrupted` after restart.
- **Tests for orchestration flow** — Added coverage for spawn completion + announce, list/history tools, stop behavior, and restart recovery.

### Changed

- **Handler tool surface** — Subagent tool definitions are now exposed in normal chat tool-capable flows (not in subagent child turns), and handler context includes explicit guidance to delegate long/parallel tasks via subagents.
- **Tool trace naming** — Added friendly trace labels/actions for subagent tools (`Subagents (spawn/list/history/send/stop)`).

---

## [1.3.4] - 2026-02-14

### Added

- **`asta doc --fix` auto-remediation mode** — `doc` now supports `--fix` to auto-repair common setup issues:
  - create backend venv + install backend deps
  - install frontend dependencies
  - create `backend/.env` from `.env.example` when missing
  - create `workspace/USER.md` template when missing

### Changed

- **Skill/tool dependency diagnostics in `doc`** — `asta doc` now checks enabled skill availability via `/api/settings/skills` and reports missing dependencies/action hints.
- **Optional dependency auto-install for skills** — in `doc --fix`, installable skill dependency issues with `install_cmd` are attempted automatically; non-installable cases are reported as manual actions.
- **CLI/docs update** — command help and docs now document `doc --fix` usage.

---

## [1.3.3] - 2026-02-14

### Changed

- **Settings: Ollama model picker reliability** — Replaced browser-dependent Ollama datalist suggestions with explicit dropdown selectors for both default AI model and fallback-provider model configuration, while keeping manual custom tag input.
- **Dashboard channels polish** — Channels card now uses clearer connected/disconnected badges, softer consistent card borders, and only shows WhatsApp when the bridge is actually connected.
- **Docs consistency pass** — Updated README/SPEC wording to match the current dashboard structure and release version.

---

## [1.3.2] - 2026-02-14

### Changed

- **Documentation consistency pass** — Updated README and workspace docs to clearly document Asta's two skill types:
  built-in Python skills (e.g. Spotify/reminders/weather/files) and OpenClaw-style workspace `SKILL.md` skills.
- **Workspace docs corrected** — Removed outdated wording that implied all selected skill bodies are pre-injected;
  docs now reflect the on-demand `read` flow for workspace skills.
- **`TOOLS.md` clarified** — Documented as user/local context notes (hosts, device names, preferences), not executable tools.
- **WhatsApp labeling** — User-facing labels now mark WhatsApp as **Beta** in panel/CLI/docs.

---

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

- **Exec: OpenClaw-style (tool only)** — Apple Notes and other exec-based skills now work like OpenClaw: the model calls an **exec tool** with a command (e.g. `memo notes`); the backend runs it and returns the result; the model replies from that output. No proactive run or pre-injected note content. Fallback: `[ASTA_EXEC: command][/ASTA_EXEC]` in the reply still works when the provider doesn't support tools. See `docs/SPEC.md` §4.2.
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
