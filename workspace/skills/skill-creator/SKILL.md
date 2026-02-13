---
name: skill-creator
description: Create or update Agent Skills (OpenClaw/Asta format). Use when designing, structuring, or packaging skills with SKILL.md, scripts, and assets. Skills go in workspace/skills/ and can be shared or downloaded from OpenClaw.
---

# Skill Creator (OpenClaw / Asta)

Create and package skills in the same format as OpenClaw and Atomic Bot. Skills are folders under **workspace/skills/** with a **SKILL.md** file. You can download skills from OpenClaw and drop them into workspace/skills/ to use in Asta.

## Directory layout

```
workspace/skills/<skill-id>/
├── SKILL.md          # Required — frontmatter + instructions
├── reference.md      # Optional — detailed docs
├── examples.md       # Optional — usage examples
└── scripts/          # Optional — utility scripts
```

## SKILL.md format

Every skill needs YAML frontmatter and a markdown body:

```markdown
---
name: my-skill-id
description: What this skill does. Use when the user asks for X or mentions Y.
homepage: https://optional-link
metadata: {}   # optional, e.g. emoji, requires.bins
---

# My Skill

Instructions, commands, examples.
```

- **name**: Lowercase, hyphens; unique id (e.g. `weather-wttr`, `apple-notes`).
- **description**: Critical for selection. Asta matches the user message against this. Include **what** it does and **when** to use it (trigger phrases).

## Description best practices

1. **Third person**: "Processes Excel files" not "I can process".
2. **Specific + trigger terms**: "Manage Apple Notes via the memo CLI. Use when the user asks to add a note, list notes, search notes, or manage note folders."
3. **WHAT and WHEN**: What the skill does; when the agent should use it.

## Adding skills from OpenClaw

OpenClaw (Atomic Bot) uses the same layout. To use an OpenClaw skill in Asta:

1. Copy the skill folder from OpenClaw (e.g. `openclaw/workspace/skills/spotify-player/`) into **workspace/skills/**.
2. Ensure **SKILL.md** has `name` and `description` in the frontmatter.
3. The skill will appear in Asta Settings → Skills and can be toggled on/off.

Relative paths in SKILL.md are resolved against the skill directory (parent of SKILL.md).

## Creating a new skill

1. **Discover**: Purpose, trigger scenarios, storage (workspace/skills/<id>/).
2. **Design**: Skill id (lowercase-hyphens), description (what + when), sections.
3. **Implement**: Create folder, write SKILL.md with frontmatter and body, add reference/scripts if needed.
4. **Verify**: Description includes trigger terms; file references are under the skill dir.

## Quick template

```markdown
---
name: my-tool
description: One-line what it does. Use when the user asks for X, Y, or Z.
---

# My Tool

## Quick start
Steps or commands.

## Notes
Optional details.
```

Keep SKILL.md under ~500 lines; put long reference in separate files and link from SKILL.md.

## Paths

- Skill dir: `workspace/skills/<skill-id>/`.
- Relative paths in SKILL.md (e.g. `scripts/helper.sh`) resolve to that directory.
- The AI has access to allowed paths (Settings → Allowed paths). If it needs a path not yet allowed, it will request access and you can grant it.
