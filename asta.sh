#!/bin/bash
#═══════════════════════════════════════════════════════════════════════════════
#  Asta - Backend + Frontend control script
#═══════════════════════════════════════════════════════════════════════════════
#
#  Usage:
#    ./asta.sh start     Start backend + frontend (stop anything on ports first)
#    ./asta.sh stop      Stop backend + frontend
#    ./asta.sh restart   Stop then start both (reliable)
#    ./asta.sh status    Show whether backend and frontend are running
#
#  Uses PID files + lsof so restarts work even when processes stick on ports.
#
#═══════════════════════════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
PID_FILE="$SCRIPT_DIR/.asta.pid"
FRONTEND_PID_FILE="$SCRIPT_DIR/.asta-frontend.pid"
LOG_FILE="$SCRIPT_DIR/backend.log"
FRONTEND_LOG_FILE="$SCRIPT_DIR/frontend.log"
BACKEND_PORT=8000
FRONTEND_PORT=5173

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
NC='\033[0m'

# Nice ANSI "ASTA" word (shown on start / restart / status / help)
print_asta_banner() {
    echo -e "${CYAN}"
    echo -e "   ${BOLD}╭─────────────╮${NC}"
    echo -e "   ${CYAN}║${NC}  ${BOLD}${MAGENTA}A S T A${NC}  ${CYAN}║${NC}"
    echo -e "   ${CYAN}╰─────────────╯${NC}"
    echo -e "${NC}"
}

print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[✓]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[!]${NC} $1"; }
print_error() { echo -e "${RED}[✗]${NC} $1"; }
print_step() { echo -e "${BLUE}[→]${NC} $1"; }

# Kill any process on a specific port (lsof works reliably across systems)
kill_port() {
    local port=$1
    local pids
    if command -v lsof >/dev/null 2>&1; then
        pids=$(lsof -ti:"$port" 2>/dev/null)
    else
        # fallback: fuser (Linux)
        pids=$(fuser "$port/tcp" 2>/dev/null)
    fi
    if [ -n "$pids" ]; then
        echo "$pids" | xargs kill -9 2>/dev/null
        return 0
    fi
    return 1
}

# Stop Asta backend
stop_backend() {
    print_step "Stopping Asta backend..."

    if [ -f "$PID_FILE" ]; then
        pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            kill -9 "$pid" 2>/dev/null
            print_success "Killed backend process (PID: $pid)"
        fi
        rm -f "$PID_FILE"
    fi

    pkill -9 -f "uvicorn.*app.main:app" 2>/dev/null

    if kill_port "$BACKEND_PORT"; then
        print_success "Freed port $BACKEND_PORT"
    fi

    sleep 2
    print_success "Backend stopped"
}

# Stop Asta frontend (Vite dev server)
stop_frontend() {
    print_step "Stopping Asta frontend..."

    if [ -f "$FRONTEND_PID_FILE" ]; then
        pid=$(cat "$FRONTEND_PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            kill -9 "$pid" 2>/dev/null
            print_success "Killed frontend process (PID: $pid)"
        fi
        rm -f "$FRONTEND_PID_FILE"
    fi

    pkill -9 -f "vite.*$FRONTEND_DIR" 2>/dev/null

    if kill_port "$FRONTEND_PORT"; then
        print_success "Freed port $FRONTEND_PORT"
    fi

    sleep 1
    print_success "Frontend stopped"
}

# Stop backend + frontend
stop_all() {
    stop_backend
    stop_frontend
}

# Start the backend server
start_backend() {
    print_step "Starting Asta backend..."

    if [ ! -d "$BACKEND_DIR" ]; then
        print_error "Backend directory not found: $BACKEND_DIR"
        return 1
    fi

    if [ ! -f "$BACKEND_DIR/.venv/bin/activate" ]; then
        print_error "Virtualenv not found. Run: cd backend && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
        return 1
    fi

    for _ in 1 2 3 4 5; do
        if lsof -Pi ":$BACKEND_PORT" -sTCP:LISTEN -t >/dev/null 2>&1 || (command -v fuser >/dev/null 2>&1 && fuser "$BACKEND_PORT/tcp" >/dev/null 2>&1); then
            print_warning "Port $BACKEND_PORT in use; freeing it..."
            kill_port "$BACKEND_PORT"
            sleep 2
        else
            break
        fi
    done
    sleep 1

    cd "$BACKEND_DIR" || return 1
    if [ -f "$LOG_FILE" ]; then
        size=$(stat -c%s "$LOG_FILE" 2>/dev/null || stat -f%z "$LOG_FILE" 2>/dev/null)
        if [ -n "$size" ] && [ "$size" -gt 10485760 ]; then
            mv "$LOG_FILE" "$LOG_FILE.old"
        fi
    fi
    echo "" >> "$LOG_FILE"
    echo "========================================" >> "$LOG_FILE"
    echo "Asta backend starting: $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"
    echo "========================================" >> "$LOG_FILE"

    nohup bash -c "source .venv/bin/activate && exec uvicorn app.main:app --host 0.0.0.0 --port $BACKEND_PORT" >> "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    pid=$(cat "$PID_FILE")

    print_status "Waiting for backend..."
    sleep 4

    if lsof -Pi ":$BACKEND_PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then
        print_success "Backend started (PID: $pid, port: $BACKEND_PORT)"
        return 0
    else
        print_error "Backend may have failed to start. Check: $LOG_FILE"
        tail -15 "$LOG_FILE"
        rm -f "$PID_FILE"
        return 1
    fi
}

# Start the frontend (Vite dev server)
start_frontend() {
    print_step "Starting Asta frontend..."

    if [ ! -d "$FRONTEND_DIR" ]; then
        print_warning "Frontend directory not found: $FRONTEND_DIR (skipping frontend)"
        return 0
    fi

    if [ ! -f "$FRONTEND_DIR/package.json" ]; then
        print_warning "Frontend package.json not found (skipping frontend)"
        return 0
    fi

    for _ in 1 2 3; do
        if lsof -Pi ":$FRONTEND_PORT" -sTCP:LISTEN -t >/dev/null 2>&1 || (command -v fuser >/dev/null 2>&1 && fuser "$FRONTEND_PORT/tcp" >/dev/null 2>&1); then
            print_warning "Port $FRONTEND_PORT in use; freeing it..."
            kill_port "$FRONTEND_PORT"
            sleep 1
        else
            break
        fi
    done
    sleep 1

    cd "$FRONTEND_DIR" || return 0
    echo "" >> "$FRONTEND_LOG_FILE"
    echo "========================================" >> "$FRONTEND_LOG_FILE"
    echo "Asta frontend starting: $(date '+%Y-%m-%d %H:%M:%S')" >> "$FRONTEND_LOG_FILE"
    echo "========================================" >> "$FRONTEND_LOG_FILE"

    nohup npm run dev >> "$FRONTEND_LOG_FILE" 2>&1 &
    echo $! > "$FRONTEND_PID_FILE"
    pid=$(cat "$FRONTEND_PID_FILE")

    print_status "Waiting for frontend..."
    sleep 3

    if lsof -Pi ":$FRONTEND_PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then
        print_success "Frontend started (PID: $pid, port: $FRONTEND_PORT)"
        return 0
    else
        # Vite can take a bit; check log for errors
        if [ -f "$FRONTEND_LOG_FILE" ]; then
            tail -5 "$FRONTEND_LOG_FILE"
        fi
        print_success "Frontend process started (PID: $pid). If needed, check: $FRONTEND_LOG_FILE"
        return 0
    fi
}

show_status() {
    echo ""
    if lsof -Pi ":$BACKEND_PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then
        pid=$(lsof -ti:"$BACKEND_PORT" 2>/dev/null | head -1)
        print_success "Backend running (PID: $pid, port: $BACKEND_PORT)"
        echo "   → http://localhost:$BACKEND_PORT"
    else
        print_warning "Backend not running"
    fi
    if lsof -Pi ":$FRONTEND_PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then
        pid=$(lsof -ti:"$FRONTEND_PORT" 2>/dev/null | head -1)
        print_success "Frontend running (PID: $pid, port: $FRONTEND_PORT)"
        echo "   → http://localhost:$FRONTEND_PORT"
    else
        print_warning "Frontend not running"
    fi
    echo ""
}

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
        ;;
    restart)
        print_asta_banner
        stop_all
        sleep 2
        start_backend
        start_frontend
        show_status
        ;;
    status)
        print_asta_banner
        show_status
        ;;
    help|--help|-h|"")
        print_asta_banner
        echo "  ./asta.sh start     Start backend + frontend (frees ports first)"
        echo "  ./asta.sh stop      Stop backend + frontend"
        echo "  ./asta.sh restart   Restart both (reliable)"
        echo "  ./asta.sh status    Show status"
        echo ""
        ;;
    *)
        print_error "Unknown command: $1"
        echo "  Use: ./asta.sh start | stop | restart | status | help"
        exit 1
        ;;
esac

exit 0
