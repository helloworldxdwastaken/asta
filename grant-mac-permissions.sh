#!/bin/bash
# grant-mac-permissions.sh
# Run this ONCE to pre-approve macOS TCC/automation permissions for Asta.
# This stops the repeated "Allow access?" popups for Notes, Contacts,
# Calendar, Reminders, and gog/memo CLI tools.
#
# Usage: ./grant-mac-permissions.sh
#
# What it does:
#   1. Opens System Settings to the relevant Privacy pages so you can
#      manually toggle the switches (required for TCC — cannot be done
#      non-interactively without SIP disabled).
#   2. Runs a quick osascript to trigger the "Allow?" dialog for the
#      apps/binaries that Asta uses, so you can approve them all at once.

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

ok()   { printf "${GREEN}✓${NC}  %s\n" "$*"; }
info() { printf "${CYAN}▸${NC}  %s\n" "$*"; }
warn() { printf "${YELLOW}⚠${NC}  %s\n" "$*"; }
err()  { printf "${RED}✕${NC}  %s\n" "$*"; }

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BACKEND_PY="$SCRIPT_DIR/backend/.venv/bin/python3"
if [ ! -f "$BACKEND_PY" ]; then
    BACKEND_PY=$(command -v python3 || true)
fi

echo ""
echo "  ┌─────────────────────────────────────────────────────┐"
echo "  │   Asta — macOS Permission Setup                     │"
echo "  │   This grants automation access to avoid repeated   │"
echo "  │   permission popups for Notes, Calendar, gog, etc.  │"
echo "  └─────────────────────────────────────────────────────┘"
echo ""

# ── 1. Grant Automation permissions via osascript (triggers the dialog) ──────

info "Triggering automation permission dialogs..."
info "(A dialog will appear for each app — click Allow/OK each time)"
echo ""

# Notes
info "Requesting access to Notes.app..."
osascript -e '
    tell application "Notes"
        -- lightweight touch to trigger TCC dialog
        set _count to count of notes
    end tell
' 2>/dev/null && ok "Notes.app: permission dialog triggered" || warn "Notes.app: may already be denied — see step 3 below"

sleep 0.5

# Contacts
info "Requesting access to Contacts.app..."
osascript -e '
    tell application "Contacts"
        set _count to count of people
    end tell
' 2>/dev/null && ok "Contacts.app: permission dialog triggered" || warn "Contacts.app: may already be denied"

sleep 0.5

# Calendar
info "Requesting access to Calendar.app..."
osascript -e '
    tell application "Calendar"
        set _count to count of calendars
    end tell
' 2>/dev/null && ok "Calendar.app: permission dialog triggered" || warn "Calendar.app: may already be denied"

sleep 0.5

# Reminders
info "Requesting access to Reminders.app..."
osascript -e '
    tell application "Reminders"
        set _count to count of lists
    end tell
' 2>/dev/null && ok "Reminders.app: permission dialog triggered" || warn "Reminders.app: may already be denied"

echo ""

# ── 2. Grant permission for the Python venv binary specifically ───────────────

if [ -f "$BACKEND_PY" ]; then
    info "Granting Automation permission for Asta's Python ($BACKEND_PY)..."
    # Run a short osascript FROM the venv Python to trigger TCC for that binary
    "$BACKEND_PY" -c "
import subprocess, sys
result = subprocess.run(
    ['osascript', '-e', 'tell application \"Notes\" to return count of notes'],
    capture_output=True, text=True, timeout=5
)
print('Notes access:', 'ok' if result.returncode == 0 else 'denied - approve in System Settings')
" 2>/dev/null && ok "Venv Python automation dialog triggered" || warn "Venv Python: approve manually in System Settings (step 3)"
fi

# ── 3. Open the relevant System Settings panes ───────────────────────────────

echo ""
info "Opening System Settings → Privacy & Security → Automation..."
open "x-apple.systempreferences:com.apple.preference.security?Privacy_Automation" 2>/dev/null || \
    open "/System/Library/PreferencePanes/Security.prefPane" 2>/dev/null || \
    warn "Could not open System Settings automatically. Open manually: System Settings → Privacy & Security → Automation"

sleep 1

info "Opening System Settings → Privacy & Security → Contacts..."
open "x-apple.systempreferences:com.apple.preference.security?Privacy_Contacts" 2>/dev/null || true

sleep 0.5

info "Opening System Settings → Privacy & Security → Calendars..."
open "x-apple.systempreferences:com.apple.preference.security?Privacy_Calendars" 2>/dev/null || true

sleep 0.5

info "Opening System Settings → Privacy & Security → Reminders..."
open "x-apple.systempreferences:com.apple.preference.security?Privacy_Reminders" 2>/dev/null || true

echo ""
echo "  ┌─────────────────────────────────────────────────────┐"
echo "  │   What to do in System Settings:                    │"
echo "  │                                                     │"
echo "  │   Automation pane — enable toggles for:            │"
echo "  │     • Terminal (or iTerm2)                         │"
echo "  │     • Python 3.x / python3                        │"
echo "  │     • uvicorn / Asta backend process              │"
echo "  │     → Allow access to Notes, Calendar, Reminders  │"
echo "  │                                                     │"
echo "  │   Contacts pane — enable Terminal / Python         │"
echo "  │   Calendars pane — enable Terminal / Python        │"
echo "  │   Reminders pane — enable Terminal / Python        │"
echo "  │                                                     │"
echo "  │   After approving, restart Asta:                   │"
echo "  │     ./asta.sh restart                              │"
echo "  └─────────────────────────────────────────────────────┘"
echo ""

# ── 4. gog CLI: verify it's accessible and authenticated ─────────────────────

GOG_BIN="/opt/homebrew/bin/gog"
[ -f "$GOG_BIN" ] || GOG_BIN=$(command -v gog 2>/dev/null || true)

if [ -n "$GOG_BIN" ] && [ -x "$GOG_BIN" ]; then
    ok "gog CLI found at $GOG_BIN"
    AUTH=$("$GOG_BIN" auth list 2>/dev/null || true)
    if [ -n "$AUTH" ]; then
        ok "gog authenticated: $AUTH"
    else
        warn "gog not authenticated. Run:"
        echo "    gog auth credentials /path/to/client_secret.json"
        echo "    gog auth add your@gmail.com --services gmail,calendar,drive,contacts"
    fi
else
    warn "gog CLI not found. Install with:"
    echo "    brew install gogcli"
    echo "  Then authenticate:"
    echo "    gog auth add your@gmail.com --services gmail,calendar,drive,contacts"
fi

# ── 5. memo CLI (Apple Notes): verify ────────────────────────────────────────

MEMO_BIN=$(command -v memo 2>/dev/null || true)
if [ -n "$MEMO_BIN" ]; then
    ok "memo CLI found at $MEMO_BIN"
else
    warn "memo CLI not installed (needed for Apple Notes skill). Install with:"
    echo "    brew tap antoniorodr/memo && brew install antoniorodr/memo/memo"
fi

echo ""
ok "Done. Restart Asta after approving permissions: ./asta.sh restart"
echo ""
