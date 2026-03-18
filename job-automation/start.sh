#!/usr/bin/env bash
# ============================================================
# Start the Job Application Platform
# ============================================================
# Usage: bash start.sh
# Stops:  Ctrl+C
# ============================================================

CYAN='\033[0;36m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

# ── Activate venv ───────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo -e "${YELLOW}Virtual environment not found. Run: bash setup.sh first${NC}"
    exit 1
fi

# ── Load environment variables ──────────────────────────────
set -a
[ -f config/.env ] && source config/.env
set +a

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║  Job Application Platform                    ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════╝${NC}"
echo ""

# ── Create required directories ─────────────────────────────
mkdir -p logs/screenshots documents/resumes documents/cover_letters \
         documents/certificates documents/other

# ── Start backend API ───────────────────────────────────────
echo -e "${CYAN}▶  Starting backend API on port 8000…${NC}"
python run.py api &
API_PID=$!

# Wait for API to start
sleep 2

# Check it's up
if ! curl -sf http://localhost:8000/health &>/dev/null; then
    echo -e "${YELLOW}⚠  API may still be starting… waiting a few more seconds${NC}"
    sleep 3
fi

echo -e "${GREEN}✓  Backend API:  http://localhost:8000${NC}"
echo -e "${GREEN}✓  API Docs:     http://localhost:8000/docs${NC}"
echo ""

# ── Serve dashboard ─────────────────────────────────────────
echo -e "${CYAN}▶  Starting dashboard on port 3000…${NC}"
cd frontend
python3 -m http.server 3000 --bind 127.0.0.1 &>/dev/null &
FRONTEND_PID=$!
cd ..
sleep 1

echo -e "${GREEN}✓  Dashboard:    http://localhost:3000${NC}"
echo ""

# ── Open browser ────────────────────────────────────────────
URL="http://localhost:3000"

# Chromebook (Crostini) — use garcon-url-handler or xdg-open
if command -v garcon-url-handler &>/dev/null; then
    garcon-url-handler "$URL" &>/dev/null &
elif command -v xdg-open &>/dev/null; then
    xdg-open "$URL" &>/dev/null &
elif command -v open &>/dev/null; then
    open "$URL" &>/dev/null &
fi

echo -e "  ${YELLOW}If the browser doesn't open automatically,${NC}"
echo -e "  open this URL manually: ${GREEN}$URL${NC}"
echo ""
echo -e "  Press ${YELLOW}Ctrl+C${NC} to stop the platform"
echo ""

# ── Keep running until Ctrl+C ───────────────────────────────
cleanup() {
    echo ""
    echo -e "${CYAN}Shutting down…${NC}"
    kill $API_PID $FRONTEND_PID 2>/dev/null
    echo -e "${GREEN}Platform stopped.${NC}"
    exit 0
}
trap cleanup INT TERM

# Monitor processes
while true; do
    if ! kill -0 $API_PID 2>/dev/null; then
        echo -e "${YELLOW}API process stopped unexpectedly. Check logs/app.log${NC}"
        kill $FRONTEND_PID 2>/dev/null
        exit 1
    fi
    sleep 5
done
