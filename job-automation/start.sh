#!/usr/bin/env bash
# ============================================================
# Start the platform (backend + open dashboard)
# ============================================================
set -e
CYAN='\033[0;36m'; GREEN='\033[0;32m'; NC='\033[0m'

# Activate venv if not already active
if [ -z "$VIRTUAL_ENV" ]; then
    source .venv/bin/activate 2>/dev/null || true
fi

# Load env
set -a; source config/.env 2>/dev/null; set +a

echo ""
echo -e "${CYAN}Starting Job Application Platform...${NC}"
echo ""

# Start API in background
python run.py api &
API_PID=$!

sleep 2

echo -e "${GREEN}✓ Backend API running at http://localhost:8000${NC}"
echo -e "${GREEN}✓ API docs at          http://localhost:8000/docs${NC}"
echo ""
echo -e "${CYAN}Opening dashboard...${NC}"

# Serve dashboard
cd frontend
python3 -m http.server 3000 &
FRONTEND_PID=$!
cd ..

sleep 1

# Try to open browser
if command -v xdg-open &>/dev/null; then
    xdg-open http://localhost:3000 &>/dev/null &
elif command -v open &>/dev/null; then
    open http://localhost:3000 &>/dev/null &
fi

echo -e "${GREEN}✓ Dashboard running at http://localhost:3000${NC}"
echo ""
echo "  Press Ctrl+C to stop everything"
echo ""

# Wait for Ctrl+C
trap "kill $API_PID $FRONTEND_PID 2>/dev/null; echo 'Platform stopped.'; exit 0" INT TERM
wait
