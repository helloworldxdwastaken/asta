---
name: apple-notes
description: Mac only. Manage Apple Notes via osascript (all operations) and memo CLI (listing). Use when the user asks about Apple Notes / Notes.app / iCloud Notes — list, search, create, edit, move, delete notes or folders.
metadata:
  openclaw:
    emoji: "📝"
    os: ["darwin"]
    requires: { bins: ["memo", "osascript"] }
    install:
      - id: brew
        kind: brew
        formula: antoniorodr/memo/memo
        bins: ["memo"]
        label: Install memo via Homebrew
---

# Apple Notes

Full Apple Notes management via `osascript` (all operations) and `memo` (quick listing).

**Key rule:** Always prefer `osascript` over `memo` for any write or move operation. `memo` interactive flags (`-a`, `-e`, `-d`, `-m`, `-s`, `-ex`) require a TTY and cannot run from Asta.

## List & Read

**List all notes (all folders):**
```bash
memo notes
```

**List notes in a specific folder:**
```bash
memo notes -f "Work"
```

**List all folders with note counts:**
```bash
osascript << 'EOF'
tell application "Notes"
  set summary to {}
  repeat with f in folders
    set cnt to count of notes of f
    if cnt > 0 then set end of summary to name of f & ": " & cnt & " notes"
  end repeat
  return summary
end tell
EOF
```

**Get all folder names:**
```bash
osascript -e 'tell application "Notes" to get name of every folder'
```

**Read a note's content (returns HTML):**
```bash
osascript -e 'tell application "Notes" to get body of (first note of folder "Notes" whose name contains "Shopping")'
```

**List all notes with folder, name, modification date:**
```bash
osascript << 'EOF'
tell application "Notes"
  set result to {}
  repeat with f in folders
    if name of f is not "Recently Deleted" then
      repeat with n in notes of f
        set end of result to name of f & " | " & name of n
      end repeat
    end if
  end repeat
  return result
end tell
EOF
```

## Search

**Search notes by name or body content across all folders:**
```bash
osascript << 'EOF'
tell application "Notes"
  set matches to {}
  repeat with f in folders
    repeat with n in notes of f
      if name of n contains "bank" or body of n contains "bank" then
        set end of matches to name of f & " / " & name of n
      end if
    end repeat
  end repeat
  return matches
end tell
EOF
```

## Create

**Create a note in a folder:**
```bash
osascript -e 'tell application "Notes" to make new note at folder "Notes" with properties {name:"Title", body:"Content here"}'
```

**Create with HTML formatting:**
```bash
osascript -e 'tell application "Notes" to make new note at folder "Work" with properties {name:"Meeting", body:"<b>Agenda</b><br><ul><li>Item 1</li><li>Item 2</li></ul>"}'
```

**Note:** Body is stored and returned as HTML. Plain text works too — Notes wraps it automatically.

**Escaping single quotes in content** (use `'"'"'` pattern):
```bash
osascript -e 'tell application "Notes" to make new note at folder "Notes" with properties {name:"Test", body:"It'"'"'s working"}'
```

## Edit

**Update a note's body:**
```bash
osascript -e 'tell application "Notes" to set body of (first note of folder "Notes" whose name contains "Shopping") to "<div>Updated content</div>"'
```

**Rename a note:**
```bash
osascript -e 'tell application "Notes" to set name of (first note of folder "Notes" whose name contains "Old Title") to "New Title"'
```

## Move

**Move a note to a different folder:**
```bash
osascript -e 'tell application "Notes" to move (first note of folder "Notes" whose name contains "Shopping list") to folder "Lists"'
```

**Move all notes matching a pattern:**
```bash
osascript << 'EOF'
tell application "Notes"
  set noteList to notes of folder "Notes"
  repeat with n in noteList
    if name of n contains "bank" then move n to folder "Work"
  end repeat
end tell
EOF
```

**Bulk move by category (example — organize all notes):**
```bash
osascript << 'EOF'
tell application "Notes"
  set noteList to notes of folder "Notes"
  repeat with n in noteList
    set noteName to name of n
    if noteName contains "shop" or noteName contains "list" then
      move n to folder "Lists"
    else if noteName contains "bank" or noteName contains "work" then
      move n to folder "Work"
    end if
  end repeat
end tell
EOF
```

## Delete

**Delete a specific note:**
```bash
osascript -e 'tell application "Notes" to delete (first note of folder "Notes" whose name contains "Old junk")'
```

**Delete all notes in a folder:**
```bash
osascript -e 'tell application "Notes" to delete every note of folder "Notes" whose name is "New Note"'
```

## Folders

**Create a new folder:**
```bash
osascript -e 'tell application "Notes" to make new folder with properties {name:"Travel"}'
```

**Delete a folder (and all its notes):**
```bash
osascript -e 'tell application "Notes" to delete folder "OldFolder"'
```

## Limitations

- `memo notes -a`, `-e`, `-d`, `-m`, `-s`, `-ex` require an interactive TTY — use `osascript` instead for all write/move/delete operations.
- Notes containing images or attachments can be moved/deleted but their rich content cannot be edited via CLI.
- Body content is HTML — use `<br>`, `<b>`, `<ul>/<li>` for formatting.
- Note matching uses `contains` — if multiple notes match, use `every note ... whose name is "exact name"` for precision.
- Grant Automation access in System Settings → Privacy & Security → Automation.
