# How OpenClaw Solves Apple Notes / Exec (reference)

Reference: `reference/openclaw` (github.com/openclaw/openclaw). This doc summarizes how they handle exec and Apple Notes so we can align or improve Asta.

**Does OpenClaw have an app?** They have an **optional** macOS menu-bar companion app (`apps/macos/`). If you use OpenClaw with **only the web UI** (no desktop app installed), there is **no app** — exec runs in the Node host process, same idea as Asta’s Python backend.

---

## 1. Apple Notes skill definition

**File:** `reference/openclaw/skills/apple-notes/SKILL.md`

- **Frontmatter:** `metadata.openclaw.requires.bins: ["memo"]`, plus `install` with brew formula and `label`.
- **Content:** Docs for the model (e.g. `memo notes`, `memo notes -s "query"`). No special “don’t say Let me check” logic — the model just gets the exec tool and uses it.

So: the skill declares it **requires** `memo`; the model is taught the CLI in the skill text.

---

## 2. Exec allowlist: three ways a command is allowed

**Files:** `src/infra/exec-approvals-allowlist.ts`, `src/infra/exec-approvals-analysis.ts`, `src/node-host/invoke.ts`

A command is allowed if **any** of:

1. **Explicit allowlist** — Config `tools.exec` allowlist entries (paths/patterns).
2. **safeBins** — Config `tools.exec.safeBins` (e.g. `["memo", "which"]`). The binary must be in this set **and** pass a “safe usage” check (no path-like args that could be dangerous).
3. **Auto-allow skills** — When `autoAllowSkills` is true, they collect **skill bins** from the gateway (`skills.bins`). The gateway returns bins from **all skills present in the workspace** (from each skill’s `metadata.requires.bins` and install `bins`). If the command’s binary is in that set, it’s allowed.

So: `memo` is allowed either via `safeBins: ["memo"]` in config, or because the apple-notes skill (in the workspace) declares `requires.bins: ["memo"]` and `autoAllowSkills` is on.

**Asta:** We use env `ASTA_EXEC_ALLOWED_BINS` plus DB `exec_allowed_bins_extra`. When the user **enables** the Apple Notes skill, we add `memo` to the DB. So we only allow `memo` when the skill is enabled (stricter than OpenClaw’s “any skill in workspace” for auto-allow).

---

## 3. Resolving the binary (PATH)

**File:** `src/infra/exec-approvals-analysis.ts` — `resolveExecutablePath()`

- For a **bare name** (e.g. `memo`): they only look in **`env.PATH` / `process.env.PATH`** (split by `path.delimiter`), plus `PATHEXT` on Windows.
- No fallback to `/opt/homebrew/bin` or similar.

So if the process (gateway/node host) runs with a minimal PATH (e.g. launched by an IDE or service), `memo` can be “not found” even when installed.

**Asta:** We added `resolve_executable()` that tries `shutil.which()` first, then **fallback paths**: `/opt/homebrew/bin`, `/usr/local/bin`, `~/.local/bin`. So we find `memo` even when the backend’s PATH is minimal. **Improvement over OpenClaw** for server/IDE-style process environments.

(On macOS, OpenClaw can optionally run exec via a “Mac App Exec Host” (companion app), which may inherit a full user PATH when launched from the desktop.)

---

## 4. Web UI only: exec in the backend (same as Asta)

**File:** `src/node-host/invoke.ts`

When OpenClaw is used with **only a web UI** (no desktop/Mac app):

- On macOS they **first try** the Mac App Exec Host. If it's **unavailable** (`runViaMacAppExecHost` returns null) and `OPENCLAW_NODE_EXEC_FALLBACK` is not set to `0`, they **fall back** to running the command in the **Node host process** via `spawn` (same process that serves the gateway).
- So in "web UI only" or headless/CLI mode, **exec runs in the same backend process** — Node for them, Python for us. Permission (e.g. Apple Notes) is **per process** in both cases: the user must approve the **backend** process (e.g. run backend from Terminal and approve the dialog).

**Asta:** We run exec in the Python backend only (no companion app). So we already use the **same way** as OpenClaw when they're in web-only mode: one backend process runs exec; the user runs that process from a context where they can grant permission (e.g. Terminal).

---

## 5. Exec as a tool (model calls it)

**Files:** `src/agents/bash-tools.exec.ts`, `src/node-host/invoke.ts`

- The model gets an **exec tool** (name `"exec"`) with a **command** (string or argv). No “proactive” run before the turn.
- When the model calls the tool, the node host:
  - Evaluates allowlist (allowlist + safeBins + skillBins with autoAllowSkills).
  - On macOS may send the run to the **Mac App Exec Host** (separate process with its own environment).
  - Otherwise **spawns** with `argv[0]` (no substitution of a resolved path); the child inherits `process.env`, so PATH must contain the binary.
- Stdout/stderr (and errors) are returned as the **tool result**; the model then replies in the next turn using that output.

So: **no “Let me check” loop** — the model is expected to call the exec tool when it needs to run `memo notes`; the backend runs it and returns real output; the model answers from that. No pre-run or context injection of note content.

**Asta:** We implemented the same flow: exec is an OpenAI-format **tool**; when the model calls it with e.g. `command: "memo notes"`, we run it (with allowlist + `resolve_executable`), append the tool result to the conversation, and re-call the same provider. No proactive Apple Notes run; tool-only, like OpenClaw.

---

## 6. Background process parity

OpenClaw pairs `exec` with `process` for long-running commands:

- `exec` can return `status: "running"` + `sessionId` when backgrounded or when yield window expires.
- `process` manages those sessions: `list`, `poll`, `log`, `write`, `kill`, `clear`, `remove`.

**Asta:** now has the same companion model:

- `exec` supports `background` and `yield_ms`.
- `process` supports `list/poll/log/write/kill/clear/remove`.
- Session logs are in-memory (not persisted across backend restarts), same general behavior class as OpenClaw runtime sessions.

---

## 7. Summary: what we took from OpenClaw and what we did differently

| Aspect | OpenClaw | Asta |
|--------|----------|------|
| **Exec as tool** | Model calls `exec` tool; backend runs and returns output | Same: tool-calling with `exec`, re-call with result |
| **Allowlist** | allowlist + safeBins + autoAllowSkills (skill bins from all workspace skills) | env + DB allowlist; add bin when user **enables** skill |
| **Finding binary** | PATH only | PATH + **fallback** (/opt/homebrew/bin, /usr/local/bin, ~/.local/bin) |
| **Apple Notes skill** | SKILL.md with `requires.bins: ["memo"]`, install docs | Same idea: skill declares required bins, we parse install from SKILL.md and auto-add to allowlist when enabled |
| **"Let me check" loop** | Avoided by design: model must call exec tool to get data | Same: tool-only, no proactive run |
| **Background sessions** | `exec` + `process` tools for long-running jobs | Same companion flow (`background`/`yield_ms` + `process` actions) |
| **Where exec runs (web UI only)** | Node host process (spawn) when Mac app unavailable | Python backend (subprocess) — same idea, one backend process |

So: we **match** their exec/process companion flow and skill-based allowlist idea, and we **improve** binary resolution for environments where PATH doesn’t include Homebrew/user bins. The remaining gap is full OpenClaw-grade approval host/security orchestration.
