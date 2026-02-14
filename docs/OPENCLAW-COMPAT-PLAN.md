# OpenClaw Compatibility Plan for Asta (Single-User)

## Goal

Make Asta a practical "OpenClaw without fluff" runtime for single-user workflows:

- Keep Asta's current simple architecture.
- Add enough API/tool compatibility so most OpenClaw-style skills can run with minimal or no edits.
- Prioritize adaptation layers over full subsystem rewrites.

This plan explicitly excludes multi-user/tenant work.

---

## Current Baseline (Asta)

Already compatible in key areas:

- `SKILL.md` workspace discovery and on-demand `read`.
- `exec` + `process` core loop.
- File tools (`list_directory`, `read_file`, `write_file`, etc.).
- `reminders` and `cron` structured tools.

Main current gap: tool API surface and schema differences vs OpenClaw.

---

## Scope Definition

### In Scope

- Tool API compatibility layer (aliases + schema adapters).
- Missing high-value tools required by many skills:
  - `web_fetch`
  - `web_search` (tool-form, not only skill-side behavior)
  - `memory_search` / `memory_get` adapter over existing RAG + memories
  - coding-tool compatibility (`read`, `write`, `edit`, `apply_patch` naming/shape)
- Improved `process` feature parity where low effort (`send-keys`/`paste` style actions).
- Compatibility test harness for representative OpenClaw skills.

### Out of Scope (for this plan)

- Full OpenClaw platform parity:
  - multi-agent orchestration
  - gateway/node/canvas ecosystem
  - mobile/mac companion app architecture
- Full security model parity (approval hosts, elevated policy matrix).

---

## Delivery Strategy

Use a compatibility-first adapter approach:

1. Preserve existing Asta tools and behavior.
2. Add compatibility wrappers that accept OpenClaw-like names/params.
3. Map wrappers to existing implementations.
4. Only build new subsystems when wrapper mapping is impossible.

This keeps risk low and avoids large rewrites.

---

## Phased Roadmap

## Phase 0 - Compatibility Spec and Fixtures

Deliverables:

- Tool mapping matrix (`OpenClaw tool -> Asta tool/adapter`).
- Canonical JSON schema contracts for each adapter.
- Skill fixture set (10-20 real skills from `reference/openclaw/skills`) categorized by dependency type.
- Pass/fail rubric per fixture.

Complexity: low.

---

## Phase 1 - Thin Compatibility Layer

Objective:

Enable most text/file/exec skills without changing skill content.

Deliverables:

- Add adapter tool names and argument normalization:
  - `read` -> workspace/files read routing
  - `write` / `edit` aliasing where safe
  - `bash` alias to `exec` (if used by imported skills)
- Expand `process` actions where straightforward:
  - keep existing actions
  - add compatibility aliases or equivalent behavior for common patterns
- Add compatibility errors that are explicit and actionable.
- Unit tests for each alias and schema normalization path.

Complexity: medium.

Expected impact:

- Large chunk of OpenClaw skills that are instruction + CLI based become runnable quickly.

---

## Phase 2 - High-Value Missing Tools

Objective:

Support common OpenClaw skills that depend on retrieval and web tooling.

Deliverables:

- `web_fetch` tool:
  - safe HTTP fetch, size/time limits, plain text extraction.
- `web_search` tool:
  - structured search results in OpenClaw-like response shape.
- `memory_search` / `memory_get`:
  - adapter on top of Asta RAG + user memories.
  - deterministic output schema for skill instructions.
- Integration tests with skill fixtures that previously failed in Phase 1.

Complexity: medium-high.

Expected impact:

- Most practical "research/notes/ops" style skills work with minimal adaptation.

---

## Phase 3 - Optional Deep Compatibility

Objective:

Close the gap for advanced skills if needed.

Potential deliverables:

- `apply_patch` compatibility semantics.
- richer terminal interaction parity (`send-keys`, `paste`, PTY-specific behavior).
- partial `message`-tool emulation for single-user channel sending patterns.
- selective implementation of other frequently requested APIs based on fixture failure data.

Complexity: high (depends on selected subset).

---

## AI-Assisted Execution Model

Where AI helps most:

- Generate adapter boilerplate + schema normalizers.
- Port repetitive tool glue code.
- Produce broad unit test scaffolding from mapping tables.
- Draft fixture-based regression tests quickly.

Where AI helps less:

- Behavioral edge-case decisions.
- Security boundary design.
- Compatibility contract arbitration when OpenClaw behavior is implicit.

Recommended workflow:

1. Human defines contract for one tool adapter.
2. AI generates implementation + tests.
3. Human reviews behavior and safety.
4. Run fixture suite.
5. Iterate per failing fixture.

AI handoff protocol (for execution by another coding agent):

1. Start by producing/updating `docs/openclaw-tool-mapping.md` from real code paths.
2. For each adapter, implement code + tests in the same PR/change batch.
3. Do not start new adapters until current fixture failures are classified:
- contract mismatch
- missing tool
- behavioral mismatch
4. Maintain a machine-readable fixture status file (`pass`, `fail`, `blocked`, reason).
5. Gate completion of each phase on explicit acceptance checks:
- Phase 0: mapping and fixtures committed, rubric defined.
- Phase 1: aliases and schema normalizers tested, target fixture pass threshold reached.
- Phase 2: `web_*` and `memory_*` adapters live, integration fixtures green at target threshold.
- Phase 3: optional APIs implemented only when backed by fixture failure evidence.

---

## Risk Register

1. Schema drift risk
- Imported skills assume exact field names/types.
- Mitigation: strict contract tests for adapter responses.

2. Hidden behavioral coupling risk
- Skills rely on side effects of OpenClaw runtime, not documented in SKILL.md.
- Mitigation: fixture-driven verification and fast shims.

3. Security regression risk
- Adding aliases like `bash`/`edit` can accidentally broaden execution surface.
- Mitigation: preserve current allowlist model and enforce centralized validation.

4. Overbuilding risk
- Implementing full OpenClaw platform instead of needed compatibility.
- Mitigation: only implement APIs required by real fixture failures.

---

## Success Criteria

Phase 1 success:

- >=60% of selected OpenClaw skill fixtures run without modifying SKILL.md.

Phase 2 success:

- >=80% fixture pass rate.
- All high-priority imported skills used by this repo are green.

Overall success:

- New imported skill onboarding is "copy folder, enable skill, run" for most skills.
- Remaining failures are documented as unsupported advanced platform APIs.

---

## Immediate Next Actions

1. Build the tool mapping matrix and fixture list (Phase 0).
2. Implement `read`/`write`/`edit`/`bash` compatibility adapters first.
3. Add fixture CI job to prevent regressions.
4. Implement `web_fetch` and `memory_search` adapters next (highest compatibility gain).
