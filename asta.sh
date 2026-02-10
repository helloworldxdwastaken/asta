#!/bin/bash
#═══════════════════════════════════════════════════════════════════════════════
#  Asta - Backend + Frontend control script
#═══════════════════════════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
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

print_asta_banner() {
    echo -e "${MAGENTA}${BOLD}"
    echo "    ▄▄▄       ██████ ▄▄▄█████▓ ▄▄▄      "
    echo "   ▒████▄   ▒██    ▒ ▓  ██▒ ▓▒▒████▄    "
    echo "   ▒██  ▀█▄ ░ ▓██▄   ▒ ▓██░ ▒░▒██  ▀█▄  "
    echo "   ░██▄▄▄▄██  ▒   ██▒░ ▓██▓ ░ ░██▄▄▄▄██ "
    echo "    ▓█   ▓██▒██████▒▒  ▒██▒ ░  ▓█   ▓██▒"
    echo "    ▒▒   ▓▒█▒ ▒▓▒ ▒ ░  ▒ ░░    ▒▒   ▓▒█░"
    echo -e "     ░   ▒▒ ░ ░▒  ░ ░    ░      ░   ▒▒ ░${NC}"
    echo -e "     ${CYAN}  AI Control Plane ${GRAY}:: ${WHITE}v0.1.0${NC}\n"
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
            # Use -o args= to get the full command line, not just the name
            local pcmd
            pcmd=$(ps -p "$pid" -o args= 2>/dev/null)
            if [[ "$pcmd" == *"sshd"* ]] || [[ "$pcmd" == *"ssh"* ]]; then
                print_warning "Port $port is held by ssh/sshd (likely port forwarding). Skipping kill for PID $pid ($pcmd)."
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

stop_backend() {
    print_status "Stopping Backend..."
    
    if [ -f "$PID_FILE" ]; then
        pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            kill -9 "$pid" 2>/dev/null
            print_sub "Killed process (PID: $pid)"
        fi
        rm -f "$PID_FILE"
    fi

    pkill -9 -f "uvicorn.*app.main:app" 2>/dev/null

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
        if kill -0 "$pid" 2>/dev/null; then
            kill -9 "$pid" 2>/dev/null
            print_sub "Killed process (PID: $pid)"
        fi
        rm -f "$FRONTEND_PID_FILE"
    fi

    pkill -9 -f "vite.*$FRONTEND_DIR" 2>/dev/null

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
    *)
        print_asta_banner
        echo "Usage: ./asta.sh {start|stop|restart|status}"
        exit 1
        ;;
esac

exit 0
