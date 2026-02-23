---
name: apple-notes
description: Mac only. Manage Apple Notes via the `memo` CLI on macOS (list, search notes) and osascript (create notes). Use only when the user explicitly asks for Apple Notes / Notes.app / iCloud Notes.
homepage: https://github.com/antoniorodr/memo
metadata:
  openclaw:
    emoji: "📝"
    os: ["darwin"]
    requires: { bins: ["memo"] }
    install:
      - id: brew
        kind: brew
        formula: antoniorodr/memo/memo
        bins: ["memo"]
        label: Install memo via Homebrew
---

# Apple Notes

Manage Apple Notes using `memo` (list/search) and `osascript` (create).

## Setup

- Install (Homebrew): `brew tap antoniorodr/memo && brew install antoniorodr/memo/memo`
- Grant Automation access to Notes.app in System Settings → Privacy & Security → Automation.
- macOS-only.

## List Notes

List all notes:
```bash
memo notes
```

Filter by folder:
```bash
memo notes -f "Work"
```

List all folders:
```bash
memo notes -fl
```

## Create a Note (non-interactive)

Use `osascript` to create a note without needing a TTY:
```bash
osascript -e 'tell application "Notes"
  tell account "iCloud"
    make new note at folder "Notes" with properties {name:"Note Title", body:"Note body here"}
  end tell
end tell'
```

Create in a specific folder:
```bash
osascript -e 'tell application "Notes"
  tell account "iCloud"
    make new note at folder "Work" with properties {name:"Meeting notes", body:"- Item 1\n- Item 2"}
  end tell
end tell'
```

**Important:** Escape any single quotes in the content by ending the string, inserting `"'"`, and re-opening:
- `body:"It'"'"'s a note"` → `It's a note`

## Search Notes

Fuzzy search:
```bash
memo notes -s "search term"
```

Note: `-s` opens an interactive selector. For non-interactive search, use `memo notes` and filter output.

## Limitations

- `memo notes -a`, `-e`, `-d`, `-m`, `-ex` require an interactive TTY — they **cannot be run from Asta**. For editing or deleting, tell the user to open Notes.app manually.
- Notes containing images or attachments cannot be edited via CLI.
- For automation, confirm Asta has Automation access to Notes.app in System Settings.
