# TOOLS.md - Your Local Notes

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that's unique to your setup.

## What goes here

- Camera names and locations
- SSH hosts and aliases
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

## Example

```markdown
### SSH
- home-server → 192.168.1.100, user: admin

### TTS
- Preferred voice: "Nova"
- Default speaker: Kitchen HomePod
```

---

## Notion

API key is configured in backend/.env as NOTION_API_KEY.

Fill in the page/database IDs below so Asta knows where to save things.
To find an ID: open the page in Notion → copy the URL → the ID is the last 32 characters.

```
### Notion Page / Database IDs
- Meeting notes parent page:  _(paste page ID here)_
- Research / summaries page:  _(paste page ID here)_
- General notes page:         _(paste page ID here)_
```

---

---

## Generated Documents & Files

When creating any document, spreadsheet, or data file (CSV, XLSX, PPTX, DOCX, PDF, etc.) always save it to **`workspace/office_docs/`** — never to the workspace root, Desktop, or other locations unless the user explicitly asks.

- `workspace/office_docs/` → all generated documents (CSV, spreadsheets, reports, presentations, word docs, PDFs)
- `workspace/scripts/` → scripts created for task automation
- `workspace/notes/` → text notes

---

## Bulk / Multi-Step Tasks

For any task that requires the same operation on many items (organizing notes, moving files, batch renaming, processing a list), **always write a single script and run it in one exec call** — never loop the same tool call one item at a time.

- Shell tasks → write a `.sh` script to `workspace/scripts/tmp/` and exec it
- AppleScript tasks → write a `.applescript` to `workspace/scripts/tmp/` and run with `osascript`
- Python tasks → write a `.py` script to `workspace/scripts/tmp/` and run with `python3`

The script handles all items in one shot. After execution, delete the script file (or it gets cleaned up automatically every night).

---

## Architecture

- **Frontend / UI**: The cross-platform desktop app (`MACWinApp/asta-app/`) built with Tauri v2 + React/TypeScript — this is what the user interacts with. Builds for macOS (DMG) and Windows (MSI).
- **Backend**: FastAPI server at `backend/` — handles chat, tools, skills, Telegram bot.
- When asked to make UI or frontend changes, the target is always the Tauri desktop app (`MACWinApp/asta-app/src/`).

---

Add whatever helps. Asta reads this at context build.
