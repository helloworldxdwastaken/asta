# AGENTS.md - Asta Workspace (OpenClaw-style)

This workspace is your home. Asta injects this and the files below into context.

## Every session

- **SOUL.md** — who Asta is (tone, boundaries).
- **USER.md** — who you are (name, preferences, context).
- **TOOLS.md** — your local notes (camera names, SSH hosts, device nicknames).
- **skills/** — each folder with `SKILL.md` is a skill; when the task matches its description, Asta uses those instructions.

## Memory

- Use RAG (Learning skill) for long-term learned knowledge.
- For session continuity, the chat history and connected channels are in context.

## Safety

- Don't exfiltrate private data.
- Don't run destructive commands without asking.
- When in doubt, ask.

---

_Edit this file to add your own conventions. Asta reads it at the start of each context build._
