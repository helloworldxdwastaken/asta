# OpenClaw-Style Workspace & Skills

Asta can use an **OpenClaw-style workspace**: context files (AGENTS.md, USER.md, etc.) and **SKILL.md**-based skills, so you can adapt Asta to your setup like Atomic Bot / OpenClaw.

## Workspace directory

- **Default:** `workspace/` at the project root (next to `backend/`).
- **Override:** set `ASTA_WORKSPACE_DIR` in `backend/.env` to any path.

If the directory doesn’t exist, workspace features are skipped (no error).

## Context files (injected into every context)

| File       | Purpose |
|-----------|---------|
| **AGENTS.md** | Workspace rules, memory, safety. “This folder is home.” |
| **USER.md**   | **Who you are:** name, timezone, location, preferences. This is the single place for user context; put e.g. `**Location:** City, Country` for time/weather/reminders. Edited in the repo. |
| **SOUL.md**   | Who Asta is: tone, boundaries, personality. |
| **TOOLS.md**  | Your local notes: SSH hosts, device names, TTS preferences. |

Create these in the workspace root. Asta reads them at the start of each context build. **User context lives under workspace only** (workspace/USER.md); there is no separate data folder for “user” identity.

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

- **Eligibility:** Asta considers the skill eligible if significant words from `description` appear in the user message.
- **Context:** When the skill is selected, the full contents of `SKILL.md` are injected into the prompt under `[SKILL: <name>]`.
- **Toggle:** Workspace skills appear in **Settings → Skills** and can be enabled/disabled like built-in skills.

You can copy skills from Atomic Bot’s `openclaw/workspace/skills/` or write your own.

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
- Only these Telegram user IDs can send messages; others get “You’re not authorized to use this bot.”
- Leave empty to allow anyone with the bot token (default).

To get your Telegram user ID: message [@userinfobot](https://t.me/userinfobot) or check the bot’s updates.

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
