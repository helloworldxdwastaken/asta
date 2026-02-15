# OpenClaw-Style Workspace & Skills

Asta can use an **OpenClaw-style workspace**: context files (AGENTS.md, USER.md, etc.) and **SKILL.md**-based skills, so you can adapt Asta to your setup like Atomic Bot / OpenClaw.

## Workspace directory

- **Default:** `workspace/` at the project root (next to `backend/`).
- **Override:** set `ASTA_WORKSPACE_DIR` in `backend/.env` to any path.

If the directory doesn’t exist, Asta creates it automatically.

## Context files (injected into every context)

| File       | Purpose |
|-----------|---------|
| **AGENTS.md** | Workspace rules, memory, safety. “This folder is home.” |
| **USER.md**   | **Who you are:** name, timezone, location, preferences. This is the single place for user context; put e.g. `**Location:** City, Country` for time/weather/reminders. Edited in the repo. |
| **SOUL.md**   | Who Asta is: tone, boundaries, personality. |
| **TOOLS.md**  | Your local notes: SSH hosts, device names, TTS preferences. Not executable tools. |

Create these in the workspace root. Asta reads them at the start of each context build. **User context lives under workspace only** (`workspace/USER.md`); there is no separate data folder for “user” identity.

## Skills from SKILL.md (workspace skills)

Put skills in:

```text
workspace/
  skills/
    <skill-id>/
      SKILL.md
```

**SKILL.md** must have YAML frontmatter with at least:

- `name` — skill id (e.g. `weather-wttr`). Use lowercase, hyphens.
- `description` — when to use this skill (Asta matches the user message against this).

Example:

```markdown
---
name: my-tool
description: Do X when the user asks about Y. Use when ...
---

# My Tool

Instructions for the AI (commands, examples, notes).
```

- **Selection:** Workspace skills are selected OpenClaw-style from `<available_skills>` by the model, then loaded with the `read` tool on demand.
- **Context:** `SKILL.md` is **not** preloaded for all skills. Only the selected skill file is read.
- **Toggle:** Workspace skills appear in **Settings → Skills** and can be enabled/disabled like built-in skills.
- **Runtime eligibility (OpenClaw-style):** Skills with `metadata.openclaw.os` and `requires.bins` are only exposed to the model when they match the current host and required binaries are present. Example: `apple-notes` is hidden on Linux and unavailable until `memo` exists on macOS.
- **Notes policy:** Generic “notes” requests go to the workspace `notes` skill (`workspace/notes/*.md`). `apple-notes` is only used when the user explicitly asks for Apple Notes / Notes.app / iCloud Notes / `memo`.

You can copy skills from Atomic Bot’s `openclaw/workspace/skills/` or write your own.

## Built-in vs workspace skills

Asta has two skill types:

- **Built-in skills (Python code):** Spotify, reminders, weather, files, etc. These do **not** use `SKILL.md`; they are selected by intent routing in code.
- **Workspace skills (`SKILL.md`):** Imported/custom OpenClaw-style skills under `workspace/skills/`. The model picks and reads one on demand.

## Skill-creator and OpenClaw skills

- **workspace/skills/skill-creator/** — Skill that helps you create and package skills (same format as OpenClaw). Use when designing or writing a new skill.
- **Using OpenClaw skills in Asta:** Copy any skill folder from OpenClaw (e.g. `openclaw/workspace/skills/spotify-player/`) into **workspace/skills/**. Ensure `SKILL.md` has `name` and `description` in the frontmatter. The skill appears in Settings → Skills.

## Self-awareness skill

When the user asks about Asta (features, how to use it, documentation), the **self-awareness** skill runs. It injects Asta’s README and `docs/*.md` into context so the model can answer from the real docs. User context (who you are) comes from **workspace/USER.md**; no separate data folder is used. Enable or disable the skill in **Settings → Skills**.

## Path access (OpenClaw-style)

- **Allowlist:** File access is limited to env `ASTA_ALLOWED_PATHS` + paths you **grant** in the UI. The workspace root is always allowed when a workspace is set.
- **Grant access:** When you or the AI needs a path that isn’t allowed, open **Files**, try to open that path (or a file inside it). If access is denied, the page shows **Grant access**; click it to add that path to your allowlist. Stored per user in the DB.
- **AI:** If the user asks for a file outside the allowlist, the AI is instructed to tell them to open Files and use “Grant access”.

## Telegram allowlist (OpenClaw-style)

To restrict who can use the Telegram bot:

- In `backend/.env` set:
  - `ASTA_TELEGRAM_ALLOWED_IDS=6168747695,123456789`
- Use numeric Telegram sender IDs only (`@username` entries are ignored).
- Only these Telegram user IDs can send messages; others get “You’re not authorized to use this bot.”
- Leave empty to allow anyone with the bot token (default).

To get your Telegram user ID: message [@userinfobot](https://t.me/userinfobot) or check the bot’s updates.

## Telegram runtime controls

From Telegram chat, you can control core runtime behavior without opening the panel:

- `/status` — server health card
- `/exec_mode` — exec security mode (`deny/allowlist/full`)
- `/allow` — add an exec binary to allowlist persistently
- `/allowlist` — show current effective exec allowlist
- `/approvals` — list pending exec approval requests
- `/approve` — approve pending exec request (`once|always`)
- `/deny` — deny pending exec request
- `/thinking` — thinking level (`off/low/medium/high`)
- `/reasoning` — reasoning visibility (`off/on/stream`)

## Summary

| Feature | Config | Location |
|--------|--------|----------|
| Workspace root | `ASTA_WORKSPACE_DIR` or `workspace/` | Context files + `skills/*/SKILL.md` (auto-created if missing) |
| Context files | (none) | `AGENTS.md`, `USER.md`, `SOUL.md`, `TOOLS.md` (workspace root). **User** = workspace/USER.md only. |
| Workspace skills | (none) | `workspace/skills/<id>/SKILL.md` |
| Skill-creator | (none) | `workspace/skills/skill-creator/SKILL.md` |
| Path allowlist | Env + DB (grant in Files UI) | OpenClaw-style request access |
| Telegram allowlist | `ASTA_TELEGRAM_ALLOWED_IDS` | Backend only |

This makes Asta “OpenClaw-adapted”: same workspace, skill format, and path management, with Asta’s backend, providers, and Telegram/WhatsApp integration.
