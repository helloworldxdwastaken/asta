---
name: notes
description: Save and manage quick notes, meeting notes, or lists in the workspace. Use when the user says "note that", "add a note", "save this", "quick note", "write that down", "add to my notes", or "create a note".
metadata: {"clawdbot":{"emoji":"📝","os":["darwin","linux"]}}
---

# Notes (OpenClaw-style)

Save notes and lists to **`notes/`** (workspace-relative) so they persist and can be read later. Uses the same file-creation convention as the files skill.

## When to use

- User says: "note that", "add a note", "save this", "quick note", "write that down", "add to my notes", "remember this", "create a note", "take a note".
- User wants to save a list, a quote, meeting points, or any short text for later.

## How to save a note

1. **Single note** – Use the file-creation block with a path under `notes/`:
   - `[ASTA_WRITE_FILE: notes/quick-note.md]`
   - content here
   - `[/ASTA_WRITE_FILE]`

2. **Named note** – If the user gives a title, use a sanitized filename (lowercase, hyphens):
   - "Note: Shopping list" → `notes/shopping-list.md`
   - "Save as meeting-2024-02" → `notes/meeting-2024-02.md`

3. **Appending** – If the user says "add to my notes" and you already have a note file, you cannot append via this convention (only full-file write). Prefer creating a new file like `notes/note-2024-02-13.md` or suggest they ask to "read my note X" and then "add Y to it" (you would need to output a new file with old content + new).

4. **Date in filename** – For quick notes without a name, use the date: `notes/2024-02-13.md` or `notes/note-2024-02-13.md`.

## Example

User: "Note that we're meeting Tuesday 3pm."

Output the content, then add:
```
[ASTA_WRITE_FILE: notes/2024-02-13.md]
# Quick note
- Meeting Tuesday 3pm
[/ASTA_WRITE_FILE]
```

After the block is processed, Asta will confirm e.g. "I've saved that to `…/workspace/notes/2024-02-13.md`."

## Reading notes

If the user asks "what's in my notes" or "read my note about X", use the **files** skill context: list or read from `notes/` (do **not** prefix with `workspace/` in tool paths). You can describe how to open the file in the panel or summarize if you have path access.

## Requirements

- Workspace must be set (default: project `workspace/`). Notes are stored under `workspace/notes/` on disk, but tool paths should be workspace-relative like `notes/my-note.md`.
- The files skill’s file-creation convention is used; no extra install.
