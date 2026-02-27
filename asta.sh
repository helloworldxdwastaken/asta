#!/bin/bash
#═══════════════════════════════════════════════════════════════════════════════
#  Asta - Backend control script
#═══════════════════════════════════════════════════════════════════════════════

# Resolve symlink to find real source dir
SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
  DIR="$( cd -P "$( dirname "$SOURCE" )" >/dev/null 2>&1 && pwd )"
  SOURCE="$(readlink "$SOURCE")"
  [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
done
SCRIPT_DIR="$( cd -P "$( dirname "$SOURCE" )" >/dev/null 2>&1 && pwd )"
BACKEND_DIR="$SCRIPT_DIR/backend"
PID_FILE="$SCRIPT_DIR/.asta.pid"
LOG_FILE="$SCRIPT_DIR/backend.log"
BACKEND_PORT=8010

# Colors
RED='\033[38;5;196m'
GREEN='\033[38;5;46m'
YELLOW='\033[38;5;226m'
BLUE='\033[38;5;39m'
CYAN='\033[38;5;51m'
MAGENTA='\033[38;5;213m'
GRAY='\033[38;5;240m'
WHITE='\033[38;5;255m'
BOLD='\033[1m'
NC='\033[0m'

cecho() {
    # Consistent color-capable output (avoids literal "-e" artifacts on some shells).
    printf "%b\n" "$*"
}

get_version() {
    if [ -f "$SCRIPT_DIR/VERSION" ]; then
        cat "$SCRIPT_DIR/VERSION" | tr -d '\n'
    else
        echo "0.1.0"
    fi
}

print_asta_banner() {
    local version
    version="$(get_version)"
    cecho "${BLUE}${BOLD}"
    echo "    ▄▄▄       ██████ ▄▄▄█████▓ ▄▄▄      "
    echo "   ▒████▄   ▒██    ▒ ▓  ██▒ ▓▒▒████▄    "
    echo "   ▒██  ▀█▄ ░ ▓██▄   ▒ ▓██░ ▒░▒██  ▀█▄  "
    echo "   ░██▄▄▄▄██  ▒   ██▒░ ▓██▓ ░ ░██▄▄▄▄██ "
    echo "    ▓█   ▓██▒██████▒▒  ▒██▒ ░  ▓█   ▓██▒"
    echo "    ▒▒   ▓▒█▒ ▒▓▒ ▒ ░  ▒ ░░    ▒▒   ▓▒█░"
    cecho "     ░   ▒▒ ░ ░▒  ░ ░    ░      ░   ▒▒ ░${NC}"
    cecho "     ${WHITE}Asta Control Plane${GRAY} · ${WHITE}v${version}${NC}\n"

    check_updates
}

check_updates() {
    # Check for .git and git command
    if [ -d "$SCRIPT_DIR/.git" ] && command -v git &> /dev/null; then
        # Attempt fetch with 1s timeout to avoid blocking
        # Use quiet mode, fetch only main to be fast
        timeout 1s git -C "$SCRIPT_DIR" fetch -q origin main 2>/dev/null
        
        # Compare hashes
        LOCAL=$(git -C "$SCRIPT_DIR" rev-parse HEAD 2>/dev/null)
        REMOTE=$(git -C "$SCRIPT_DIR" rev-parse origin/main 2>/dev/null)
        
        if [ -n "$REMOTE" ] && [ "$LOCAL" != "$REMOTE" ]; then
            # Check if we are behind (Remote is reachable from Local? No, Local reachable from Remote)
            # If Local is ancestor of Remote, we are behind.
            BASE=$(git -C "$SCRIPT_DIR" merge-base HEAD origin/main 2>/dev/null)
            if [ "$LOCAL" = "$BASE" ]; then
                cecho "    ${YELLOW}⚠  New version available! Run './asta.sh update' to upgrade.${NC}\n"
            fi
        fi
    fi
}

print_status() { cecho "  ${CYAN}▸${NC} $1"; }
print_success() { cecho "  ${GREEN}●${NC} $1"; }
print_warning() { cecho "  ${YELLOW}◆${NC} $1"; }
print_error() { cecho "  ${RED}✕${NC} $1"; }
print_sub() { cecho "    ${GRAY}${1}${NC}"; }

pid_cwd() {
    local pid=$1
    if ! command -v lsof >/dev/null 2>&1; then
        return 1
    fi
    lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p' | head -n 1
}


# Kill any process on a specific port (lsof works reliably across systems)
kill_port() {
    local port=$1
    local pids
    if command -v lsof >/dev/null 2>&1; then
        pids=$(lsof -ti:"$port" 2>/dev/null)
    else
        pids=$(fuser "$port/tcp" 2>/dev/null)
    fi
    
    if [ -n "$pids" ]; then
        for pid in $pids; do
            # Check process name/cmd to avoid killing sshd (port forwarding)
            # Use -o args= to get the full command line
            local pcmd
            pcmd=$(ps -p "$pid" -o args= 2>/dev/null)
            
            # Whitelist approach: Only kill if it looks like OUR specific app
            # Generic "node" or "python" is too broad — could match IDE/editor processes
            if [[ "$pcmd" == *"uvicorn"*"app.main"* ]] || \
               [[ "$pcmd" == *"$BACKEND_DIR"* ]]; then
                # Safe to kill — matches our app
                 :
            else
                print_warning "Port $port is held by unknown process (PID $pid: $pcmd). Skipping kill to protect SSH/System."
                continue
            fi

            # Kill nicely first
            kill -15 "$pid" 2>/dev/null
            sleep 0.5
            if kill -0 "$pid" 2>/dev/null; then
                kill -9 "$pid" 2>/dev/null
            fi
        done
        return 0
    fi
    return 1
}

# Prefer Python 3.12 or 3.13 for backend (ChromaDB/pydantic don't support 3.14 yet)
find_backend_python() {
    for cmd in python3.12 python3.13 python3; do
        if command -v "$cmd" &>/dev/null; then
            local ver
            ver=$("$cmd" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null)
            if [ "$cmd" = "python3" ] && [ -n "$ver" ]; then
                # Avoid 3.14+
                local major minor
                major="${ver%%.*}"
                minor="${ver#*.}"
                minor="${minor%%.*}"
                if [ "$major" -eq 3 ] && [ "${minor:-0}" -ge 14 ]; then
                    continue
                fi
            fi
            echo "$cmd"
            return 0
        fi
    done
    echo ""
    return 1
}

# Create backend .venv with correct Python and install deps (idempotent if .venv exists)
ensure_backend_venv() {
    if [ -f "$BACKEND_DIR/.venv/bin/activate" ]; then
        return 0
    fi
    local py
    py=$(find_backend_python)
    if [ -z "$py" ]; then
        print_error "No suitable Python found. Backend needs Python 3.12 or 3.13 (3.14 not supported). Install: brew install python@3.12"
        return 1
    fi
    print_status "Creating backend virtualenv (using $py)..."
    (cd "$BACKEND_DIR" && "$py" -m venv .venv) || return 1
    print_sub "Installing backend dependencies..."
    (cd "$BACKEND_DIR" && source .venv/bin/activate && pip install -r requirements.txt) || return 1
    print_success "Backend venv ready."
    return 0
}

# Helper: safely kill a PID only if its command matches an allowed pattern
safe_kill_pid() {
    local pid=$1
    shift
    local patterns=("$@")  # allowed command substrings

    if ! kill -0 "$pid" 2>/dev/null; then
        return 1  # not running
    fi

    local pcmd
    pcmd=$(ps -p "$pid" -o args= 2>/dev/null)
    if [ -z "$pcmd" ]; then
        return 1
    fi

    local matched=false
    for pat in "${patterns[@]}"; do
        if [[ "$pcmd" == *"$pat"* ]]; then
            matched=true
            break
        fi
    done

    if ! $matched; then
        print_warning "PID $pid doesn't look like our app ($pcmd). Skipping to protect SSH."
        return 1
    fi

    # Graceful stop first, then force
    kill -15 "$pid" 2>/dev/null
    sleep 0.5
    if kill -0 "$pid" 2>/dev/null; then
        kill -9 "$pid" 2>/dev/null
    fi
    return 0
}

# Kill stale backend-local processes that still hold sqlite files
# even when they no longer listen on the backend port.
release_backend_db_locks() {
    local db_path="$BACKEND_DIR/asta.db"
    if [ ! -f "$db_path" ] || ! command -v lsof >/dev/null 2>&1; then
        return 1
    fi

    local pids
    pids=$(lsof -t "$db_path" 2>/dev/null | sort -u)
    if [ -z "$pids" ]; then
        return 1
    fi

    local released=0
    for p in $pids; do
        if ! kill -0 "$p" 2>/dev/null; then
            continue
        fi
        local cwd pcmd
        cwd=$(pid_cwd "$p" 2>/dev/null || true)
        pcmd=$(ps -p "$p" -o args= 2>/dev/null)

        # Safety: only kill if it clearly belongs to this backend workspace.
        if [[ "$cwd" == "$BACKEND_DIR" ]] || [[ "$pcmd" == *"$BACKEND_DIR"* ]]; then
            if safe_kill_pid "$p" "python" "uvicorn" "$BACKEND_DIR"; then
                print_sub "Released DB lock holder (PID: $p)"
                released=1
            fi
        fi
    done

    if [ "$released" -eq 1 ]; then
        return 0
    fi
    return 1
}

update_asta() {
    print_status "Updating Asta..."
    cd "$SCRIPT_DIR" || exit 1
    
    if ! command -v git &> /dev/null; then
        print_error "Git not found. Cannot update."
        return 1
    fi
    
    if [ ! -d ".git" ]; then
        print_error "Not a git repository. Cannot update."
        return 1
    fi
    
    # Fetch so we know what we're pulling
    print_sub "Fetching from origin..."
    git fetch origin 2>/dev/null || true
    
    # Check for uncommitted local changes
    local dirty did_stash=0
    dirty=$(git status --porcelain 2>/dev/null)
    if [ -n "$dirty" ]; then
        echo ""
        print_warning "You have local changes. Pulling may overwrite or conflict with:"
        git status --short 2>/dev/null | while read -r line; do
            cecho "  ${GRAY}  $line${NC}"
        done
        echo ""
        
        # Non-interactive: respect env or exit with instructions
        if [ ! -t 0 ]; then
            if [ "$ASTA_UPDATE_FORCE" = "stash" ]; then
                print_sub "ASTA_UPDATE_FORCE=stash → stashing, pulling, then popping stash..."
                git stash push -m "asta update $(date +%Y%m%d-%H%M%S)" || return 1
                did_stash=1
            elif [ "$ASTA_UPDATE_FORCE" = "discard" ]; then
                print_sub "ASTA_UPDATE_FORCE=discard → discarding local changes and pulling..."
                git reset --hard HEAD
                git clean -fd
            else
                print_error "Update aborted (local changes). To proceed non-interactively:"
                cecho "  ${WHITE}  ASTA_UPDATE_FORCE=stash   ./asta.sh update${NC}   # stash, pull, then stash pop"
                cecho "  ${WHITE}  ASTA_UPDATE_FORCE=discard ./asta.sh update${NC}   # discard local changes and pull"
                echo ""
                return 1
            fi
        else
            # Interactive: ask
            cecho "  ${CYAN}[s]${NC} Stash changes, pull, then re-apply (recommended)"
            cecho "  ${CYAN}[d]${NC} Discard local changes and pull (overwrites your changes)"
            cecho "  ${CYAN}[c]${NC} Cancel"
            echo ""
            read -r -p "  Continue? [s/d/c] (default: s): " choice
            choice=${choice:-s}
            case "$choice" in
                s|S)
                    print_sub "Stashing local changes..."
                    git stash push -m "asta update $(date +%Y%m%d-%H%M%S)" || { print_error "Stash failed."; return 1; }
                    did_stash=1
                    ;;
                d|D)
                    print_sub "Discarding local changes..."
                    git reset --hard HEAD
                    git clean -fd
                    ;;
                c|C)
                    print_warning "Update cancelled."
                    return 0
                    ;;
                *)
                    print_warning "Unknown choice. Cancelling."
                    return 0
                    ;;
            esac
        fi
    fi
    
    print_sub "Pulling from origin..."
    if git pull; then
        if [ "$did_stash" = "1" ]; then
            print_sub "Re-applying your local changes..."
            if ! git stash pop; then
                print_warning "Stash pop had conflicts. Resolve them and run 'git stash drop' when done, or keep with 'git stash apply'."
            fi
        fi
        print_success "Code updated. Restarting services..."
        stop_all
        echo ""
        cecho "  ${GRAY}─────────────────────────────────────────${NC}"
        echo ""
        start_backend
        echo ""
        cecho "  ${GRAY}─────────────────────────────────────────${NC}"
        show_status
    else
        print_error "Git pull failed."
        if [ "$did_stash" = "1" ]; then
            print_sub "Your changes are in 'git stash list'. Restore with: git stash pop"
        fi
        return 1
    fi
}

install_asta() {
    print_status "Installing 'asta' command to system..."
    local target="/usr/local/bin/asta"
    local source="$SCRIPT_DIR/asta.sh"
    
    print_sub "Source: $source"
    print_sub "Target: $target"
    
    # Create data/ and User.md if not present
    mkdir -p "$SCRIPT_DIR/data"
    if [ ! -f "$SCRIPT_DIR/data/User.md" ]; then
        printf '%s\n' "# About you" "" "- **Location:** " "- **Preferred name:** " "- **Important:**" "  - " > "$SCRIPT_DIR/data/User.md"
        print_sub "Created data/User.md"
    fi
    
    cmd="ln -sf \"$source\" \"$target\""
    
    if [ -w "/usr/local/bin" ]; then
        eval "$cmd"
        print_success "Installed! You can now run 'asta' from anywhere."
    else
        print_warning "Need sudo permissions to write to /usr/local/bin."
        cecho "Run this command manually:\n"
        cecho "    ${WHITE}sudo $cmd${NC}\n"
    fi
}

stop_backend() {
    print_status "Stopping Backend..."
    
    if [ -f "$PID_FILE" ]; then
        pid=$(cat "$PID_FILE")
        if safe_kill_pid "$pid" "python" "uvicorn"; then
            print_sub "Killed process (PID: $pid)"
        fi
        rm -f "$PID_FILE"
    fi

    # Safely kill any remaining uvicorn processes (validate each PID)
    local uv_pids
    uv_pids=$(pgrep -f "uvicorn.*app.main:app" 2>/dev/null)
    for p in $uv_pids; do
        safe_kill_pid "$p" "python" "uvicorn"
    done

    if kill_port "$BACKEND_PORT"; then
        print_sub "Freed port $BACKEND_PORT"
    fi

    # Kill any root-owned uvicorn on our port (can happen if asta was once started with sudo)
    local root_pids
    root_pids=$(pgrep -f "uvicorn.*app.main:app" 2>/dev/null)
    for p in $root_pids; do
        local owner
        owner=$(ps -o user= -p "$p" 2>/dev/null | tr -d ' ')
        if [ "$owner" = "root" ]; then
            sudo kill -9 "$p" 2>/dev/null && print_sub "Killed root uvicorn (PID: $p)" \
                || print_warning "Could not kill root process $p — run: sudo kill -9 $p"
        fi
    done

    # If a stale backend-local python process still holds sqlite, release it.
    if release_backend_db_locks; then
        print_sub "Cleared stale SQLite lock holder(s)"
    fi

    # Check if really stopped
    if lsof -Pi ":$BACKEND_PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then
        print_warning "Port $BACKEND_PORT still in use!"
    else
        print_success "Backend stopped"
    fi
}


stop_all() {
    stop_backend
}

start_backend() {
    echo ""
    print_status "Starting Backend..."

    # Guard: running as root breaks macOS Automation (Apple Notes, osascript, etc.)
    if [ "$(id -u)" = "0" ]; then
        print_error "Do not run asta.sh as root (sudo). Apple Notes and other macOS integrations require running as your user account."
        print_sub "Run without sudo: ./asta.sh start"
        return 1
    fi

    if [ ! -d "$BACKEND_DIR" ]; then
        print_error "Directory not found: $BACKEND_DIR"
        return 1
    fi

    if [ ! -f "$BACKEND_DIR/.venv/bin/activate" ]; then
        if ! ensure_backend_venv; then
            print_error "Backend needs Python 3.12 or 3.13. Install: brew install python@3.12. Then: cd backend && python3.12 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
            return 1
        fi
    fi

    # Ensure port is free
    for _ in 1 2 3 4 5; do
        if lsof -Pi ":$BACKEND_PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then
            print_sub "Port $BACKEND_PORT busy, freeing..."
            kill_port "$BACKEND_PORT"
            sleep 1
        else
            break
        fi
    done

    cd "$BACKEND_DIR" || return 1
    
    # Log rotation
    if [ -f "$LOG_FILE" ]; then
        size=$(stat -c%s "$LOG_FILE" 2>/dev/null || stat -f%z "$LOG_FILE" 2>/dev/null)
        if [ -n "$size" ] && [ "$size" -gt 5242880 ]; then # 5MB
            mv "$LOG_FILE" "$LOG_FILE.old"
        fi
    fi
    
    echo "--- Restart: $(date) ---" >> "$LOG_FILE"

    # Auto-start Tailscale on this machine so it's reachable remotely
    if command -v tailscale &>/dev/null || [ -f /Applications/Tailscale.app/Contents/MacOS/Tailscale ]; then
        TS_BIN=$(command -v tailscale 2>/dev/null || echo "/Applications/Tailscale.app/Contents/MacOS/Tailscale")
        TS_STATE=$("$TS_BIN" status --json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('BackendState',''))" 2>/dev/null || echo "")
        if [ "$TS_STATE" = "Stopped" ] || [ "$TS_STATE" = "" ]; then
            print_sub "Starting Tailscale..."
            "$TS_BIN" up --accept-routes 2>/dev/null &
        fi
        TS_IP=$("$TS_BIN" ip --4 2>/dev/null | head -1)
        [ -n "$TS_IP" ] && print_sub "Tailscale IP: $TS_IP (port $BACKEND_PORT)"
    fi

    nohup bash -c "source '$BACKEND_DIR/.venv/bin/activate' && export PATH='$BACKEND_DIR/.venv/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin' && cd '$BACKEND_DIR' && exec uvicorn app.main:app --host 0.0.0.0 --port $BACKEND_PORT" >> "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    pid=$(cat "$PID_FILE")

    # Wait for startup (first run can take 20s+ due to ChromaDB/sentence-transformers)
    print_sub "Waiting for boot..."
    for i in {1..25}; do
        sleep 1
        if lsof -Pi ":$BACKEND_PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then
            print_success "Backend active (PID: $pid)"
            return 0
        fi
    done

    print_error "Backend did not respond in time. Check logs (first start can be slow):"
    print_sub "$LOG_FILE"
    tail -15 "$LOG_FILE"
    rm -f "$PID_FILE"
    return 1
}


# $1 = "full" to include skills list (only for `asta status`; restart/update/start use short)
show_status() {
    local full="${1:-}"
    echo ""
    cecho "  ${GRAY}─────────────────────────────────────────${NC}"
    cecho "  ${WHITE}${BOLD}system status${NC}"
    cecho "  ${GRAY}─────────────────────────────────────────${NC}"
    
    # Backend
    if lsof -Pi ":$BACKEND_PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then
        pid=$(lsof -ti:"$BACKEND_PORT" 2>/dev/null | head -1)
        print_success "backend   ${GREEN}up${NC}  ${GRAY}pid $pid${NC}"
    else
        print_error "backend   ${RED}down${NC}"
    fi

    # Separator before server/channels/skills
    if lsof -Pi ":$BACKEND_PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then
        cecho "  ${GRAY}─────────────────────────────────────────${NC}"
    fi

    # Rich status from API (server, channels; skills only when full)
    if lsof -Pi ":$BACKEND_PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then
        if [ -f "$BACKEND_DIR/cli_status.py" ]; then
            if [ "$full" = "full" ]; then
                export ASTA_STATUS_FULL=1
            else
                unset -v ASTA_STATUS_FULL 2>/dev/null || true
            fi
            if [ -f "$BACKEND_DIR/.venv/bin/python" ]; then
                "$BACKEND_DIR/.venv/bin/python" "$BACKEND_DIR/cli_status.py" 2>/dev/null || true
            else
                python3 "$BACKEND_DIR/cli_status.py" 2>/dev/null || true
            fi
        fi
    fi
    cecho "  ${GRAY}─────────────────────────────────────────${NC}"
    echo ""
}

print_commands() {
    cecho "${WHITE}Commands:${NC}"
    cecho "  ${CYAN}start${NC}    Start backend"
    cecho "  ${CYAN}stop${NC}     Stop all services"
    cecho "  ${CYAN}restart${NC}  Restart all services"
    cecho "  ${CYAN}status${NC}   Show service status + integrations"
    cecho "  ${CYAN}doc${NC}      Safe diagnostics (alias: doctor). Use --fix to auto-fix setup/deps"
    cecho "  ${CYAN}update${NC}   Pull latest code and restart"
    cecho "  ${CYAN}install${NC}  Symlink asta to /usr/local/bin"
    cecho "  ${CYAN}setup${NC}    Create backend venv (Python 3.12/3.13)"
    cecho "  ${CYAN}version${NC}  Show version"
    echo ""
}

doc_create_workspace_user() {
    local user_file="$SCRIPT_DIR/workspace/USER.md"
    mkdir -p "$SCRIPT_DIR/workspace"
    if [ ! -f "$user_file" ]; then
        cat > "$user_file" <<'EOF'
# About you

- **Preferred name:** 
- **Location:** 
- **Timezone:** 
- **Important:** 
  - 
EOF
    fi
}

doc_api_python() {
    if [ -f "$BACKEND_DIR/.venv/bin/python" ]; then
        echo "$BACKEND_DIR/.venv/bin/python"
        return 0
    fi
    if command -v python3 >/dev/null 2>&1; then
        echo "python3"
        return 0
    fi
    echo ""
    return 1
}

doc_check_skill_dependencies() {
    # $1 = 1 to auto-fix installable dependency issues
    local fix_mode="$1"
    local api_py
    api_py=$(doc_api_python)
    if [ -z "$api_py" ]; then
        print_warning "skill deps   ${YELLOW}skip${NC}  ${GRAY}python not available for API check${NC}"
        return 0
    fi
    if ! lsof -Pi ":$BACKEND_PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then
        print_warning "skill deps   ${YELLOW}skip${NC}  ${GRAY}backend not running (start Asta to inspect skills)${NC}"
        return 0
    fi

    local line exit_code
    while IFS=$'\t' read -r kind a b c; do
        case "$kind" in
            ISSUE)
                print_warning "skill dep    ${YELLOW}${a}${NC}  ${GRAY}${b}${NC}"
                ;;
            FIXED)
                print_success "skill dep    ${GREEN}fixed${NC}  ${GRAY}${a}${NC}"
                ;;
            FAILED)
                print_warning "skill dep    ${YELLOW}auto-fix failed${NC}  ${GRAY}${a}: ${b}${NC}"
                ;;
            MANUAL)
                print_warning "skill dep    ${YELLOW}manual${NC}  ${GRAY}${a}: ${b}${NC}"
                ;;
            SUMMARY)
                local total fixed remaining
                total="$a"
                fixed="$b"
                remaining="$c"
                if [ "${total:-0}" -eq 0 ]; then
                    print_success "skill deps   ${GREEN}ok${NC}  ${GRAY}all enabled skills available${NC}"
                else
                    print_warning "skill deps   ${YELLOW}${remaining}/${total} unresolved${NC}  ${GRAY}${fixed} auto-fixed${NC}"
                fi
                ;;
            ERROR)
                print_warning "skill deps   ${YELLOW}check failed${NC}  ${GRAY}${a}${NC}"
                ;;
        esac
    done < <(
        ASTA_ROOT="$SCRIPT_DIR" "$api_py" - "$BACKEND_PORT" "$fix_mode" <<'PY'
import json
import os
import subprocess
import sys
import urllib.request

port = int(sys.argv[1])
fix_mode = sys.argv[2] == "1"
root = os.environ.get("ASTA_ROOT", ".")
url = f"http://localhost:{port}/api/settings/skills?user_id=default"

def fetch_skills():
    with urllib.request.urlopen(url, timeout=4) as r:
        if r.status != 200:
            raise RuntimeError(f"HTTP {r.status}")
        data = json.loads(r.read().decode("utf-8"))
    return data.get("skills", []) if isinstance(data, dict) else []

try:
    skills = fetch_skills()
except Exception as e:
    print("ERROR\t" + str(e).replace("\n", " ")[:220])
    raise SystemExit(2)

issues = [s for s in skills if s.get("enabled") and not s.get("available")]
fixed = 0

for s in issues:
    name = str(s.get("name") or s.get("id") or "unknown").strip()
    hint = str(s.get("action_hint") or "missing dependency").strip()
    install_cmd = str(s.get("install_cmd") or "").strip()
    auto_fixable = bool(install_cmd) and ("install" in hint.lower() or "exec" in hint.lower())
    print(f"ISSUE\t{name}\t{hint}\t{'yes' if auto_fixable else 'no'}")
    if fix_mode:
        if auto_fixable:
            p = subprocess.run(
                install_cmd,
                shell=True,
                cwd=root,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            if p.returncode == 0:
                fixed += 1
                print(f"FIXED\t{name}\t\t")
            else:
                out = (p.stdout or "").strip().replace("\n", " ")
                print(f"FAILED\t{name}\t{out[:180]}\t")
        else:
            print(f"MANUAL\t{name}\t{hint}\t")

remaining = len(issues)
if fix_mode and fixed > 0:
    try:
        skills_after = fetch_skills()
        remaining = len([s for s in skills_after if s.get("enabled") and not s.get("available")])
    except Exception:
        pass

print(f"SUMMARY\t{len(issues)}\t{fixed}\t{remaining}")
PY
    )
    exit_code=$?
    return "$exit_code"
}

run_doc() {
    local fix_mode=0
    if [ "$1" = "--fix" ]; then
        fix_mode=1
    fi
    local issues=0
    echo ""
    cecho "  ${GRAY}─────────────────────────────────────────${NC}"
    if [ "$fix_mode" -eq 1 ]; then
        cecho "  ${WHITE}${BOLD}doc${NC}  ${GRAY}(safe diagnostics + auto-fix)${NC}"
    else
        cecho "  ${WHITE}${BOLD}doc${NC}  ${GRAY}(safe diagnostics)${NC}"
    fi
    cecho "  ${GRAY}─────────────────────────────────────────${NC}"

    local py
    py=$(find_backend_python)
    if [ -n "$py" ]; then
        print_success "python    ${GREEN}ok${NC}  ${GRAY}$py${NC}"
    else
        print_error "python    ${RED}missing${NC}  ${GRAY}need Python 3.12 or 3.13${NC}"
        issues=1
    fi

    if [ -f "$BACKEND_DIR/.venv/bin/activate" ]; then
        print_success "backend venv   ${GREEN}present${NC}"
    else
        if [ "$fix_mode" -eq 1 ]; then
            print_warning "backend venv   ${YELLOW}missing${NC}  ${GRAY}attempting auto-fix${NC}"
            if ensure_backend_venv; then
                print_success "backend venv   ${GREEN}fixed${NC}"
            else
                print_error "backend venv   ${RED}failed to fix${NC}"
                issues=1
            fi
        else
            print_warning "backend venv   ${YELLOW}missing${NC}  ${GRAY}run ./asta.sh setup${NC}"
            issues=1
        fi
    fi

    if [ -f "$BACKEND_DIR/.env" ]; then
        print_success "backend .env   ${GREEN}present${NC}"
    else
        if [ "$fix_mode" -eq 1 ] && [ -f "$SCRIPT_DIR/.env.example" ]; then
            cp "$SCRIPT_DIR/.env.example" "$BACKEND_DIR/.env"
            print_success "backend .env   ${GREEN}fixed${NC}  ${GRAY}copied from .env.example${NC}"
        else
            print_warning "backend .env   ${YELLOW}missing${NC}  ${GRAY}copy from .env.example${NC}"
            issues=1
        fi
    fi

    if [ -f "$SCRIPT_DIR/workspace/USER.md" ]; then
        print_success "workspace user ${GREEN}present${NC}"
    else
        if [ "$fix_mode" -eq 1 ]; then
            doc_create_workspace_user
            print_success "workspace user ${GREEN}fixed${NC}  ${GRAY}created workspace/USER.md${NC}"
        else
            print_warning "workspace user ${YELLOW}missing${NC}  ${GRAY}create workspace/USER.md${NC}"
        fi
    fi

    local api_ok=0
    if lsof -Pi ":$BACKEND_PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then
        local api_py=""
        api_py=$(doc_api_python)

        if [ -n "$api_py" ]; then
            if "$api_py" - "$BACKEND_PORT" <<'PY'
import json, sys, urllib.request
port = int(sys.argv[1])
url = f"http://localhost:{port}/api/health"
try:
    with urllib.request.urlopen(url, timeout=2) as r:
        data = json.loads(r.read().decode("utf-8"))
        ok = (r.status == 200 and str(data.get("status", "")).lower() == "ok")
except Exception:
    ok = False
if not ok:
    raise SystemExit(1)
PY
            then
                print_success "api health   ${GREEN}ok${NC}  ${GRAY}/api/health${NC}"
                api_ok=1
            else
                print_warning "api health   ${YELLOW}unreachable${NC}  ${GRAY}backend process is up but API is not responding${NC}"
                issues=1
            fi
        fi
    fi
    if [ "$api_ok" -eq 1 ]; then
        if ! doc_check_skill_dependencies "$fix_mode"; then
            issues=1
        fi
    else
        print_warning "skill deps   ${YELLOW}skip${NC}  ${GRAY}api not ready (start Asta to inspect skills)${NC}"
    fi

    show_status full

    if [ "$issues" -eq 0 ]; then
        print_success "Doc checks passed."
    else
        print_warning "Doc found setup issues (see warnings above)."
    fi
}

# Main CLI logic
case "$1" in
    start)
        print_asta_banner
        
        # Check if installed globally
        if ! command -v asta &> /dev/null; then
             print_warning "Tip: Run './asta.sh install' to add 'asta' to your path and run it from anywhere."
             echo ""
        fi

        stop_all
        echo ""
        cecho "  ${GRAY}─────────────────────────────────────────${NC}"
        echo ""
        start_backend
        echo ""
        cecho "  ${GRAY}─────────────────────────────────────────${NC}"
        show_status
        ;;
    stop)
        print_asta_banner
        stop_all
        echo ""
        print_success "All services stopped."
        ;;
    restart)
        print_asta_banner
        stop_all
        echo ""
        cecho "  ${GRAY}─────────────────────────────────────────${NC}"
        echo ""
        start_backend
        echo ""
        cecho "  ${GRAY}─────────────────────────────────────────${NC}"
        show_status
        ;;
    status)
        print_asta_banner
        show_status full
        ;;
    doc|doctor)
        print_asta_banner
        case "$2" in
            "")
                run_doc
                ;;
            --fix)
                run_doc --fix
                ;;
            *)
                print_error "Unknown doc option: $2"
                cecho "  ${GRAY}Use: ./asta.sh doc [--fix]${NC}"
                exit 1
                ;;
        esac
        ;;
    update)
        print_asta_banner
        update_asta
        ;;
    install)
        print_asta_banner
        install_asta
        ;;
    setup)
        print_asta_banner
        print_status "Setting up backend (Python 3.12/3.13 venv + deps)..."
        if ! ensure_backend_venv; then
            print_error "Install Python 3.12 or 3.13 (e.g. brew install python@3.12), then run ./asta.sh setup again."
            exit 1
        fi
        print_success "Setup complete. Run ./asta.sh start"
        ;;
    version)
        print_asta_banner
        ;;
    help|--help|-h)
        print_asta_banner
        print_commands
        cecho "  ${GRAY}Run: ./asta.sh <command>${NC}"
        exit 0
        ;;
    *)
        print_asta_banner
        print_commands
        cecho "  ${GRAY}Run: ./asta.sh <command>  or  asta help${NC}"
        exit 1
        ;;
esac

exit 0
