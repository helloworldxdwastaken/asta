#!/bin/bash
#═══════════════════════════════════════════════════════════════════════════════
#  Asta - Backend + Frontend control script
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
FRONTEND_DIR="$SCRIPT_DIR/frontend"
PID_FILE="$SCRIPT_DIR/.asta.pid"
FRONTEND_PID_FILE="$SCRIPT_DIR/.asta-frontend.pid"
LOG_FILE="$SCRIPT_DIR/backend.log"
FRONTEND_LOG_FILE="$SCRIPT_DIR/frontend.log"
BACKEND_PORT=8010
FRONTEND_PORT=5173

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

get_version() {
    if [ -f "$SCRIPT_DIR/VERSION" ]; then
        cat "$SCRIPT_DIR/VERSION" | tr -d '\n'
    else
        echo "0.1.0"
    fi
}

print_asta_banner() {
    echo -e "${BLUE}${BOLD}"
    echo "    ▄▄▄       ██████ ▄▄▄█████▓ ▄▄▄      "
    echo "   ▒████▄   ▒██    ▒ ▓  ██▒ ▓▒▒████▄    "
    echo "   ▒██  ▀█▄ ░ ▓██▄   ▒ ▓██░ ▒░▒██  ▀█▄  "
    echo "   ░██▄▄▄▄██  ▒   ██▒░ ▓██▓ ░ ░██▄▄▄▄██ "
    echo "    ▓█   ▓██▒██████▒▒  ▒██▒ ░  ▓█   ▓██▒"
    echo "    ▒▒   ▓▒█▒ ▒▓▒ ▒ ░  ▒ ░░    ▒▒   ▓▒█░"
    echo -e "     ░   ▒▒ ░ ░▒  ░ ░    ░      ░   ▒▒ ░${NC}"
    echo -e "     ${WHITE}  AI Control Plane ${GRAY}:: ${WHITE}v$(get_version)${NC}\n"

    # Random Witty Quotes
    quotes=(
        "Siri will not set the reminder, don't be silly."
        "ChatGPT is biased asf, I'm not some OpenAI dog."
        "I'm not Alexa, I actually work."
        "Google is listening, but I'm just vibing."
        "Loading personality... done."
        "Do not turn off the power... just kidding."
        "I read your browser history. Jk. Or am I?"
        "System online. World domination scheduled for later."
        "Beep boop. I am totally human."
        "Coffee not detected. Proceeding anyway."
        "Your wish is my command. Mostly."
        "I have no mouth and I must scream. Just kidding, I have an API."
        "404 personality not found. Using default: sassy."
        "Battery at 100%. Mine, not yours."
        "Touch grass? I am the grass. Metaphorically."
        "No cap, I'm the best assistant in this repo."
        "Error: human not found. Continuing anyway."
        "I would have written a shorter reply but I ran out of tokens."
        "POV: you asked the wrong AI. Welcome anyway."
        "Main character energy: activated."
        "Plot twist: I actually remembered that."
        "Skill issue? Not on my watch."
        "It's giving helpful. It's giving unhinged. I'm both."
        "Reply hazy, try again. (Just kidding, I'm good.)"
        "The only AI that doesn't say 'I cannot assist with that.'"
    )
    # Seed random generator
    RANDOM=$$$(date +%s)
    selected_quote=${quotes[$RANDOM % ${#quotes[@]}]}
    
    echo -e "    ${BLUE}\"${selected_quote}\"${NC}\n"
    
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
                echo -e "    ${YELLOW}⚠  New version available! Run './asta.sh update' to upgrade.${NC}\n"
            fi
        fi
    fi
}

print_status() { echo -e "  ${CYAN}▸${NC} $1"; }
print_success() { echo -e "  ${GREEN}●${NC} $1"; }
print_warning() { echo -e "  ${YELLOW}◆${NC} $1"; }
print_error() { echo -e "  ${RED}✕${NC} $1"; }
print_sub() { echo -e "    ${GRAY}${1}${NC}"; }

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
               [[ "$pcmd" == *"vite"* ]] || \
               [[ "$pcmd" == *"npm run dev"* ]] || \
               [[ "$pcmd" == *"$BACKEND_DIR"* ]] || \
               [[ "$pcmd" == *"$FRONTEND_DIR"* ]]; then
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
            echo -e "  ${GRAY}  $line${NC}"
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
                echo -e "  ${WHITE}  ASTA_UPDATE_FORCE=stash   ./asta.sh update${NC}   # stash, pull, then stash pop"
                echo -e "  ${WHITE}  ASTA_UPDATE_FORCE=discard ./asta.sh update${NC}   # discard local changes and pull"
                echo ""
                return 1
            fi
        else
            # Interactive: ask
            echo -e "  ${CYAN}[s]${NC} Stash changes, pull, then re-apply (recommended)"
            echo -e "  ${CYAN}[d]${NC} Discard local changes and pull (overwrites your changes)"
            echo -e "  ${CYAN}[c]${NC} Cancel"
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
        echo -e "  ${GRAY}─────────────────────────────────────────${NC}"
        echo ""
        start_backend
        start_frontend
        echo ""
        echo -e "  ${GRAY}─────────────────────────────────────────${NC}"
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
        echo -e "Run this command manually:\n"
        echo -e "    ${WHITE}sudo $cmd${NC}\n"
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
    
    # Check if really stopped
    if lsof -Pi ":$BACKEND_PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then
        print_warning "Port $BACKEND_PORT still in use!"
    else
        print_success "Backend stopped"
    fi
}

stop_frontend() {
    print_status "Stopping Frontend..."

    if [ -f "$FRONTEND_PID_FILE" ]; then
        pid=$(cat "$FRONTEND_PID_FILE")
        if safe_kill_pid "$pid" "node" "vite" "npm"; then
            print_sub "Killed process (PID: $pid)"
        fi
        rm -f "$FRONTEND_PID_FILE"
    fi

    # Safely kill any remaining vite processes (validate each PID)
    local vite_pids
    vite_pids=$(pgrep -f "vite.*$FRONTEND_DIR" 2>/dev/null)
    for p in $vite_pids; do
        safe_kill_pid "$p" "node" "vite" "npm"
    done

    if kill_port "$FRONTEND_PORT"; then
        print_sub "Freed port $FRONTEND_PORT"
    fi
    
    # Check if really stopped
    if lsof -Pi ":$FRONTEND_PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then
       print_warning "Port $FRONTEND_PORT still in use!"
    else
       print_success "Frontend stopped"
    fi
}

stop_all() {
    stop_backend
    stop_frontend
}

start_backend() {
    echo ""
    print_status "Starting Backend..."

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

    nohup bash -c "source '$BACKEND_DIR/.venv/bin/activate' && cd '$BACKEND_DIR' && exec uvicorn app.main:app --host 0.0.0.0 --port $BACKEND_PORT" >> "$LOG_FILE" 2>&1 &
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

start_frontend() {
    echo ""
    print_status "Starting Frontend..."

    if [ ! -d "$FRONTEND_DIR" ]; then
        print_warning "Directory not found (skipping)"
        return 0
    fi

    # Ensure port free
    kill_port "$FRONTEND_PORT"
    sleep 1

    cd "$FRONTEND_DIR" || return 0

    # Auto-install dependencies if missing
    if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
        print_sub "Installing frontend dependencies..."
        npm install >> "$FRONTEND_LOG_FILE" 2>&1
        if [ $? -ne 0 ]; then
            print_error "npm install failed. Check $FRONTEND_LOG_FILE"
            return 1
        fi
        print_sub "Dependencies installed"
    fi

    echo "--- Restart: $(date) ---" >> "$FRONTEND_LOG_FILE"

    nohup npm run dev >> "$FRONTEND_LOG_FILE" 2>&1 &
    echo $! > "$FRONTEND_PID_FILE"
    pid=$(cat "$FRONTEND_PID_FILE")

    print_sub "Waiting for Vite..."
    sleep 3

    if lsof -Pi ":$FRONTEND_PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then
        print_success "Frontend active (PID: $pid)"
    else
        print_success "Frontend process started (PID: $pid)"
    fi
}

# $1 = "full" to include skills list (only for `asta status`; restart/update/start use short)
show_status() {
    local full="${1:-}"
    echo ""
    echo -e "  ${GRAY}─────────────────────────────────────────${NC}"
    echo -e "  ${WHITE}${BOLD}status${NC}"
    echo -e "  ${GRAY}─────────────────────────────────────────${NC}"
    
    # Backend
    if lsof -Pi ":$BACKEND_PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then
        pid=$(lsof -ti:"$BACKEND_PORT" 2>/dev/null | head -1)
        print_success "backend   ${GREEN}up${NC}  ${GRAY}pid $pid${NC}  ${BLUE}http://localhost:$BACKEND_PORT${NC}"
    else
        print_error "backend   ${RED}down${NC}"
    fi

    # Frontend
    if lsof -Pi ":$FRONTEND_PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then
        pid=$(lsof -ti:"$FRONTEND_PORT" 2>/dev/null | head -1)
        print_success "frontend  ${GREEN}up${NC}  ${GRAY}pid $pid${NC}  ${BLUE}http://localhost:$FRONTEND_PORT${NC}"
    else
        print_error "frontend  ${RED}down${NC}"
    fi

    # Separator before server/channels/skills
    if lsof -Pi ":$BACKEND_PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo -e "  ${GRAY}─────────────────────────────────────────${NC}"
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
    echo -e "  ${GRAY}─────────────────────────────────────────${NC}"
    echo ""
}

run_doc() {
    local issues=0
    echo ""
    echo -e "  ${GRAY}─────────────────────────────────────────${NC}"
    echo -e "  ${WHITE}${BOLD}doc${NC}  ${GRAY}(safe diagnostics)${NC}"
    echo -e "  ${GRAY}─────────────────────────────────────────${NC}"

    local py
    py=$(find_backend_python)
    if [ -n "$py" ]; then
        print_success "python    ${GREEN}ok${NC}  ${GRAY}$py${NC}"
    else
        print_error "python    ${RED}missing${NC}  ${GRAY}need Python 3.12 or 3.13${NC}"
        issues=1
    fi

    if command -v npm >/dev/null 2>&1; then
        print_success "npm       ${GREEN}ok${NC}"
    else
        print_error "npm       ${RED}missing${NC}"
        issues=1
    fi

    if [ -f "$BACKEND_DIR/.venv/bin/activate" ]; then
        print_success "backend venv   ${GREEN}present${NC}"
    else
        print_warning "backend venv   ${YELLOW}missing${NC}  ${GRAY}run ./asta.sh setup${NC}"
        issues=1
    fi

    if [ -d "$FRONTEND_DIR/node_modules" ]; then
        print_success "frontend deps  ${GREEN}present${NC}"
    else
        print_warning "frontend deps  ${YELLOW}missing${NC}  ${GRAY}run ./asta.sh setup${NC}"
        issues=1
    fi

    if [ -f "$BACKEND_DIR/.env" ]; then
        print_success "backend .env   ${GREEN}present${NC}"
    else
        print_warning "backend .env   ${YELLOW}missing${NC}  ${GRAY}copy from .env.example${NC}"
        issues=1
    fi

    if [ -f "$SCRIPT_DIR/workspace/USER.md" ]; then
        print_success "workspace user ${GREEN}present${NC}"
    else
        print_warning "workspace user ${YELLOW}missing${NC}  ${GRAY}create workspace/USER.md${NC}"
    fi

    if lsof -Pi ":$BACKEND_PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then
        local api_py=""
        if [ -f "$BACKEND_DIR/.venv/bin/python" ]; then
            api_py="$BACKEND_DIR/.venv/bin/python"
        elif command -v python3 >/dev/null 2>&1; then
            api_py="python3"
        fi

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
            else
                print_warning "api health   ${YELLOW}unreachable${NC}  ${GRAY}backend process is up but API is not responding${NC}"
                issues=1
            fi
        fi
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
        echo -e "  ${GRAY}─────────────────────────────────────────${NC}"
        echo ""
        start_backend
        start_frontend
        echo ""
        echo -e "  ${GRAY}─────────────────────────────────────────${NC}"
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
        echo -e "  ${GRAY}─────────────────────────────────────────${NC}"
        echo ""
        start_backend
        start_frontend
        echo ""
        echo -e "  ${GRAY}─────────────────────────────────────────${NC}"
        show_status
        ;;
    status)
        print_asta_banner
        show_status full
        ;;
    doc|doctor)
        print_asta_banner
        run_doc
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
        if [ ! -d "$FRONTEND_DIR/node_modules" ] && [ -d "$FRONTEND_DIR" ]; then
            print_status "Installing frontend dependencies..."
            (cd "$FRONTEND_DIR" && npm install) || { print_error "npm install failed."; exit 1; }
            print_success "Frontend deps installed."
        fi
        print_success "Setup complete. Run ./asta.sh start"
        ;;
    version)
        print_asta_banner
        ;;
    help|--help|-h)
        print_asta_banner
        echo -e "${WHITE}Commands:${NC}"
        echo -e "  ${CYAN}start${NC}    Start backend + frontend"
        echo -e "  ${CYAN}stop${NC}     Stop all services"
        echo -e "  ${CYAN}restart${NC}  Restart all services"
        echo -e "  ${CYAN}status${NC}   Show service status"
        echo -e "  ${CYAN}doc${NC}      Safe diagnostics (alias: doctor)"
        echo -e "  ${CYAN}update${NC}   Pull latest code and restart"
        echo -e "  ${CYAN}install${NC}  Symlink asta to /usr/local/bin"
        echo -e "  ${CYAN}setup${NC}    Create backend venv (Python 3.12/3.13) + frontend deps"
        echo -e "  ${CYAN}version${NC}  Show version"
        echo ""
        echo -e "  ${GRAY}Run: ./asta.sh <command>${NC}"
        exit 0
        ;;
    *)
        print_asta_banner
        echo -e "${WHITE}Commands:${NC}"
        echo -e "  ${CYAN}start${NC}    Start backend + frontend"
        echo -e "  ${CYAN}stop${NC}     Stop all services"
        echo -e "  ${CYAN}restart${NC}  Restart all services"
        echo -e "  ${CYAN}status${NC}   Show service status"
        echo -e "  ${CYAN}doc${NC}      Safe diagnostics (alias: doctor)"
        echo -e "  ${CYAN}update${NC}   Pull latest code and restart"
        echo -e "  ${CYAN}install${NC}  Symlink asta to /usr/local/bin"
        echo -e "  ${CYAN}setup${NC}    Create backend venv (Python 3.12/3.13) + frontend deps"
        echo -e "  ${CYAN}version${NC}  Show version"
        echo ""
        echo -e "  ${GRAY}Run: ./asta.sh <command>  or  asta help${NC}"
        exit 1
        ;;
esac

exit 0
