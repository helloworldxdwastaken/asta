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
    echo -e "${MAGENTA}${BOLD}"
    echo "    ▄▄▄       ██████ ▄▄▄█████▓ ▄▄▄      "
    echo "   ▒████▄   ▒██    ▒ ▓  ██▒ ▓▒▒████▄    "
    echo "   ▒██  ▀█▄ ░ ▓██▄   ▒ ▓██░ ▒░▒██  ▀█▄  "
    echo "   ░██▄▄▄▄██  ▒   ██▒░ ▓██▓ ░ ░██▄▄▄▄██ "
    echo "    ▓█   ▓██▒██████▒▒  ▒██▒ ░  ▓█   ▓██▒"
    echo "    ▒▒   ▓▒█▒ ▒▓▒ ▒ ░  ▒ ░░    ▒▒   ▓▒█░"
    echo -e "     ░   ▒▒ ░ ░▒  ░ ░    ░      ░   ▒▒ ░${NC}"
    echo -e "     ${CYAN}  AI Control Plane ${GRAY}:: ${WHITE}v$(get_version)${NC}\n"
}

print_status() { echo -e "${CYAN}➜${NC} $1"; }
print_success() { echo -e "${GREEN}✔${NC} $1"; }
print_warning() { echo -e "${YELLOW}⚠${NC} $1"; }
print_error() { echo -e "${RED}✘${NC} $1"; }
print_sub() { echo -e "  ${GRAY}└─${NC} $1"; }

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
    
    print_sub "Pulling from origin..."
    if git pull; then
        print_success "Code updated. Restarting services..."
        stop_all
        start_backend
        start_frontend
        show_status
    else
        print_error "Git pull failed."
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
        print_error "Virtualenv missing. Run: cd backend && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
        return 1
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

    # Wait for startup
    print_sub "Waiting for boot..."
    for i in {1..7}; do
        sleep 1
        if lsof -Pi ":$BACKEND_PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then
            print_success "Backend active (PID: $pid)"
            return 0
        fi
    done

    print_error "Backend failed to start. Check logs:"
    print_sub "$LOG_FILE"
    tail -5 "$LOG_FILE"
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

show_status() {
    echo ""
    echo -e "${WHITE}${BOLD}Status Check:${NC}"
    echo "-----------------------------------"
    
    # Backend
    if lsof -Pi ":$BACKEND_PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then
        pid=$(lsof -ti:"$BACKEND_PORT" 2>/dev/null | head -1)
        print_success "Backend  : ${GREEN}Online${NC} (PID $pid)"
        echo -e "    ${GRAY}└─ ${BLUE}http://localhost:$BACKEND_PORT${NC}"
    else
        print_error "Backend  : ${RED}Offline${NC}"
    fi

    # Frontend
    if lsof -Pi ":$FRONTEND_PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then
        pid=$(lsof -ti:"$FRONTEND_PORT" 2>/dev/null | head -1)
        print_success "Frontend : ${GREEN}Online${NC} (PID $pid)"
        echo -e "    ${GRAY}└─ ${BLUE}http://localhost:$FRONTEND_PORT${NC}"
    else
        print_error "Frontend : ${RED}Offline${NC}"
    fi
    echo ""
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
        start_backend
        start_frontend
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
        start_backend
        start_frontend
        show_status
        ;;
    status)
        print_asta_banner
        show_status
        ;;
    update)
        print_asta_banner
        update_asta
        ;;
    install)
        print_asta_banner
        install_asta
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
        echo -e "  ${CYAN}update${NC}   Pull latest code and restart"
        echo -e "  ${CYAN}install${NC}  Symlink asta to /usr/local/bin"
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
        echo -e "  ${CYAN}update${NC}   Pull latest code and restart"
        echo -e "  ${CYAN}install${NC}  Symlink asta to /usr/local/bin"
        echo -e "  ${CYAN}version${NC}  Show version"
        echo ""
        echo -e "  ${GRAY}Run: ./asta.sh <command>  or  asta help${NC}"
        exit 1
        ;;
esac

exit 0
