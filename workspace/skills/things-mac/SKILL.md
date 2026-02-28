---
name: things-mac
description: Mac only. Manage Things 3 via the `things` CLI on macOS (add/update projects+todos via URL scheme; read/search/list from the local Things database). Use when a user asks to add a task to Things, list inbox/today/upcoming, search tasks, or inspect projects/areas/tags.
metadata:
  openclaw:
    emoji: "✅"
    os: ["darwin"]
    requires: { bins: ["things"] }
    install:
      - id: go
        kind: go
        module: github.com/ossianhempel/things3-cli/cmd/things@latest
        bins: ["things"]
        label: Install things3-cli (go)
---

# Things 3 CLI

Use `things` to read your local Things database (inbox/today/search/projects/areas/tags) and to add/update todos via the Things URL scheme.

## Requirements

- **Things 3 app** must be installed (Mac App Store). Without it, neither reads nor writes will work.
- Install CLI: `GOBIN=/opt/homebrew/bin go install github.com/ossianhempel/things3-cli/cmd/things@latest`
- **For DB reads:** set `THINGSDB` environment variable to your Things database folder.
  - Typical path: `~/Library/Group Containers/JLMPQHK86H.com.culturedcode.ThingsMac/ThingsData-<hash>/`
  - Find it: `ls ~/Library/Group\ Containers/JLMPQHK86H.com.culturedcode.ThingsMac/`
  - Set in shell: `export THINGSDB="$HOME/Library/Group Containers/JLMPQHK86H.com.culturedcode.ThingsMac/ThingsData-<hash>/"`
  - Or add to backend `.env`: `THINGSDB=/path/to/ThingsData-xxx`
- **Full Disk Access** required for read operations: grant it to Terminal (or Asta.app) in System Settings → Privacy & Security → Full Disk Access.
- Optional: set `THINGS_AUTH_TOKEN` for update/modify operations.

## Read-only (DB)

```bash
things inbox --limit 50
things today
things upcoming
things search "query"
things projects
things areas
things tags
```

## Write (URL scheme — opens Things app)

```bash
# Preview without creating:
things --dry-run add "Title"

# Add a task:
things add "Title" --notes "notes here" --when today --deadline 2026-06-01

# Bring Things to front when adding:
things --foreground add "Title"
```

## Add examples

```bash
things add "Buy milk"
things add "Buy milk" --notes "2% + bananas"
things add "Book flights" --list "Travel"
things add "Pack charger" --list "Travel" --heading "Before"
things add "Call dentist" --tags "health,phone"
things add "Trip prep" --checklist-item "Passport" --checklist-item "Tickets"
```

## Modify a todo (needs auth token)

```bash
# Get task ID first:
things search "milk" --limit 5

# Update:
things update --id <UUID> --auth-token <TOKEN> "New title"
things update --id <UUID> --auth-token <TOKEN> --notes "New notes"
things update --id <UUID> --auth-token <TOKEN> --append-notes "extra"
things update --id <UUID> --auth-token <TOKEN> --completed
things update --id <UUID> --auth-token <TOKEN> --canceled
```

## Notes

- macOS-only.
- `--dry-run` prints the URL and does not open Things.
- Delete is not supported by the CLI; mark as `--completed` or `--canceled` instead.
- If `THINGSDB` is not set, read operations fail with "Things database not found".
