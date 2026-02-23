---
name: notes
description: Save and manage quick notes, meeting notes, or lists in the workspace. Use when the user says "note that", "add a note", "save this", "quick note", "write that down", "add to my notes", or "create a note".
metadata: {"clawdbot":{"emoji":"📝","os":["darwin","linux"]}}
---

# Notes

Save notes and lists to `notes/` in the workspace so they persist and can be read later.

## When to use

- User says: "note that", "add a note", "save this", "quick note", "write that down", "add to my notes", "remember this", "create a note", "take a note".
- User wants to save a list, a quote, meeting points, or any short text for later.

## How to save a note

Call the **`write_file`** tool with:
- `path`: workspace-relative like `notes/shopping-list.md` or `notes/2024-02-13.md`
- `content`: the note content in markdown

**Naming rules:**
- Named note (user gives title): sanitize to lowercase + hyphens → `notes/shopping-list.md`
- Date-based (no title): `notes/note-YYYY-MM-DD.md`
- Meeting notes: `notes/meeting-YYYY-MM-DD.md`

## Examples

**Quick note:**
```
write_file(path="notes/note-2024-02-13.md", content="# Quick note\n- Meeting Tuesday 3pm")
```

**Shopping list:**
```
write_file(path="notes/shopping-list.md", content="# Shopping list\n- Milk\n- Bananas")
```

## Reading notes

If the user asks "what's in my notes" or "read my note about X":
- Use `list_directory` on the workspace `notes/` folder
- Use `read_file` to open a specific note

## Appending to a note

The `write_file` tool overwrites the file. To append:
1. `read_file` the existing note
2. Combine old content + new content
3. `write_file` with the combined content

## Notes

- Workspace-relative paths resolve to `workspace/notes/` on disk.
- Parent directories are created automatically.
- No extra binaries required.
