#!/usr/bin/env bash
# ============================================================
# Job Application Platform — One-Command Setup
# ============================================================
# Run this once to get everything ready:
#   bash setup.sh
# ============================================================

set -e
CYAN='\033[0;36m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'

print() { echo -e "${CYAN}▶ $1${NC}"; }
ok()    { echo -e "${GREEN}✓ $1${NC}"; }
warn()  { echo -e "${YELLOW}⚠ $1${NC}"; }
fail()  { echo -e "${RED}✗ $1${NC}"; }

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║   Job Application Automation Platform         ║${NC}"
echo -e "${CYAN}║   Setup Wizard for Niccolò Andrea Nolli       ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════╝${NC}"
echo ""

# ─── Python ────────────────────────────────────────────────
print "Checking Python..."
if ! command -v python3 &>/dev/null; then
    fail "Python 3 not found. Please install from https://python.org"
    exit 1
fi
PYVER=$(python3 -c "import sys; print(sys.version_info.minor)")
ok "Python 3.${PYVER} found"

# ─── Virtual environment ───────────────────────────────────
if [ ! -d ".venv" ]; then
    print "Creating virtual environment..."
    python3 -m venv .venv
    ok "Virtual environment created"
else
    ok "Virtual environment already exists"
fi

# Activate
source .venv/bin/activate
print "Installing Python dependencies..."
pip install -q -r requirements.txt
ok "Dependencies installed"

# ─── Playwright ────────────────────────────────────────────
print "Installing Playwright browser (Chromium)..."
playwright install chromium --with-deps 2>/dev/null || playwright install chromium
ok "Playwright ready"

# ─── Database ──────────────────────────────────────────────
print "Initialising database..."
python run.py init-db
ok "Database ready"

# ─── .env file ─────────────────────────────────────────────
if [ ! -f "config/.env" ]; then
    cp config/.env.example config/.env
    warn "config/.env created from template — you may want to add API keys"
else
    ok "config/.env already exists"
fi

# ─── Document directories ──────────────────────────────────
mkdir -p documents/resumes documents/cover_letters documents/certificates documents/other logs/screenshots
ok "Storage directories ready"

# ─── AI provider detection ─────────────────────────────────
echo ""
echo -e "${CYAN}── Checking AI providers ──────────────────────${NC}"

# Load .env
set -a; source config/.env; set +a

OLLAMA_OK=false
GROQ_OK=false

# Check Ollama
if curl -s --connect-timeout 2 http://localhost:11434/api/tags &>/dev/null; then
    MODELS=$(curl -s http://localhost:11434/api/tags | python3 -c "import sys,json; d=json.load(sys.stdin); print(','.join(m['name'] for m in d.get('models',[])))" 2>/dev/null)
    if echo "$MODELS" | grep -q "llama3"; then
        ok "Ollama running with LLaMA — AI is ready (FREE, local)"
        OLLAMA_OK=true
    else
        warn "Ollama is running but no LLaMA model found"
        echo "  Run: ollama pull llama3.1"
    fi
else
    warn "Ollama not running (optional — gives you free local AI)"
    echo "  Install: https://ollama.com/download"
    echo "  Then:    ollama pull llama3.1"
fi

# Check Groq
if [ -n "$GROQ_API_KEY" ] && [ "$GROQ_API_KEY" != "gsk_..." ]; then
    ok "Groq API key found — free cloud AI available"
    GROQ_OK=true
else
    warn "No Groq API key (optional free cloud AI)"
    echo "  Get a free key at: https://console.groq.com"
    echo "  Then set GROQ_API_KEY in config/.env"
fi

if [ "$OLLAMA_OK" = false ] && [ "$GROQ_OK" = false ]; then
    warn "No AI provider configured yet. Cover letter generation won't work until you set one up."
    echo "  Easiest option: get a free Groq key at https://console.groq.com"
fi

# ─── Summary ───────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   Setup Complete!                             ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo "  Next steps:"
echo ""
echo -e "  1. Start the platform:  ${CYAN}bash start.sh${NC}"
echo -e "     (or separately:)"
echo -e "     Backend:    ${CYAN}python run.py api${NC}"
echo -e "     Dashboard:  open ${CYAN}frontend/index.html${NC} in your browser"
echo ""
echo -e "  2. Upload your CV in the dashboard → Documents tab"
echo ""
echo -e "  3. Run a dry-run scrape: ${CYAN}python run.py scrape${NC}"
echo -e "     (then ${CYAN}python run.py scrape --live${NC} to save results)"
echo ""
echo -e "  4. Browse matches in the dashboard → click Apply → review letter"
echo ""
if [ -z "$TELEGRAM_BOT_TOKEN" ] || [ -z "$TELEGRAM_CHAT_ID" ]; then
    warn "Telegram not configured — set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in config/.env"
fi
echo ""
