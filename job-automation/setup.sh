#!/usr/bin/env bash
# ============================================================
# Job Application Platform — Setup Script
# Works on: Chromebook (Linux), macOS, Ubuntu/Debian, Windows WSL
# ============================================================
# Run once:  bash setup.sh
# Start app: bash start.sh
# ============================================================

set -e

# ── Colours ──────────────────────────────────────────────
CYAN='\033[0;36m'; GREEN='\033[0;32m'
YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
print() { echo -e "${CYAN}▶  $1${NC}"; }
ok()    { echo -e "${GREEN}✓  $1${NC}"; }
warn()  { echo -e "${YELLOW}⚠  $1${NC}"; }
fail()  { echo -e "${RED}✗  $1${NC}"; }
hr()    { echo -e "${CYAN}────────────────────────────────────────${NC}"; }

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║  Job Application Platform — Setup Wizard     ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════╝${NC}"
echo ""

# ── Detect OS ──────────────────────────────────────────────
OS="unknown"
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
fi
IS_CHROMEBOOK=false
if [ -d /usr/share/chromeos-assets ] || grep -q "chrome" /etc/os-release 2>/dev/null || [ -f /dev/.cros_milestone ]; then
    IS_CHROMEBOOK=true
fi
IS_MAC=false
[ "$(uname)" = "Darwin" ] && IS_MAC=true

print "Detected OS: $(uname -s)$([ "$IS_CHROMEBOOK" = true ] && echo ' (ChromeOS Linux)')"

# ── System dependencies (Chromebook / Debian / Ubuntu) ─────
if [ "$IS_MAC" = false ] && [ "$IS_CHROMEBOOK" = true ] || [ "$OS" = "debian" ] || [ "$OS" = "ubuntu" ] || [ "$OS" = "linuxmint" ]; then
    print "Installing system dependencies (sudo required)…"
    sudo apt-get update -qq
    sudo apt-get install -y -qq \
        python3 python3-pip python3-venv \
        curl wget git \
        libnss3 libatk1.0-0 libatk-bridge2.0-0 \
        libcups2 libdrm2 libxkbcommon0 libxcomposite1 \
        libxdamage1 libxfixes3 libxrandr2 libgbm1 \
        libasound2 libpango-1.0-0 libpangocairo-1.0-0 \
        libgtk-3-0 libx11-xcb1 2>/dev/null || true
    ok "System dependencies ready"
fi

# ── Python version check ────────────────────────────────────
print "Checking Python version…"
PY_CMD=""
for cmd in python3.11 python3.10 python3.9 python3; do
    if command -v "$cmd" &>/dev/null; then
        PYVER=$($cmd -c "import sys; print(sys.version_info.minor)")
        PYMAJ=$($cmd -c "import sys; print(sys.version_info.major)")
        if [ "$PYMAJ" -ge 3 ] && [ "$PYVER" -ge 9 ]; then
            PY_CMD=$cmd
            break
        fi
    fi
done

if [ -z "$PY_CMD" ]; then
    fail "Python 3.9 or higher is required."
    if [ "$IS_CHROMEBOOK" = true ]; then
        echo "  On Chromebook, run: sudo apt-get install python3.11"
    elif [ "$IS_MAC" = true ]; then
        echo "  On macOS, run: brew install python@3.11"
    fi
    exit 1
fi
ok "Python found: $PY_CMD ($PYMAJ.$PYVER)"

# ── Virtual environment ─────────────────────────────────────
if [ ! -d ".venv" ]; then
    print "Creating virtual environment…"
    $PY_CMD -m venv .venv
    ok "Virtual environment created (.venv/)"
else
    ok "Virtual environment exists (.venv/)"
fi

source .venv/bin/activate

# ── Python packages ─────────────────────────────────────────
print "Installing Python packages (this takes ~1 minute)…"
pip install -q --upgrade pip
pip install -q -r requirements.txt
ok "Python packages installed"

# ── Playwright browser ──────────────────────────────────────
print "Installing Playwright browser (Chromium)…"
echo "  This downloads ~130MB on first run."
if [ "$IS_CHROMEBOOK" = true ] || [ "$OS" = "debian" ] || [ "$OS" = "ubuntu" ]; then
    # On Linux, install deps then browser
    playwright install-deps chromium 2>/dev/null || true
fi
playwright install chromium
ok "Playwright browser ready"

# ── Database ────────────────────────────────────────────────
print "Initialising database…"
python run.py init-db
ok "Database ready (database/jobs.db)"

# ── Environment file ────────────────────────────────────────
if [ ! -f "config/.env" ]; then
    cp config/.env.example config/.env
    warn "config/.env created — add your API keys to unlock all features"
else
    ok "config/.env already exists"
fi

# ── Storage directories ─────────────────────────────────────
mkdir -p documents/resumes documents/cover_letters documents/certificates \
         documents/other logs/screenshots
ok "Storage directories ready"

# ── Load .env for checks ────────────────────────────────────
set -a; source config/.env 2>/dev/null; set +a

# ── AI provider check ───────────────────────────────────────
hr
echo ""
echo -e "${CYAN}Checking AI providers…${NC}"
echo ""

OLLAMA_OK=false; GROQ_OK=false

# Ollama
if curl -sf --connect-timeout 2 http://localhost:11434/api/tags &>/dev/null; then
    MODELS=$(curl -sf http://localhost:11434/api/tags 2>/dev/null | \
             python3 -c "import sys,json; [print(m['name']) for m in json.load(sys.stdin).get('models',[])]" 2>/dev/null || echo "")
    if echo "$MODELS" | grep -qi "llama\|mistral\|phi"; then
        ok "Ollama running — $(echo "$MODELS" | head -1) available (FREE local AI)"
        OLLAMA_OK=true
    else
        warn "Ollama is running but no model found. Run: ollama pull llama3.1"
    fi
else
    warn "Ollama not running (optional — gives you free private local AI)"
    echo "     Install: https://ollama.com/download"
    echo "     Then:    ollama pull llama3.1"
fi

echo ""

# Groq
if [ -n "$GROQ_API_KEY" ] && [ "$GROQ_API_KEY" != "gsk_..." ]; then
    ok "Groq API key found — LLaMA 3.1 70B available (FREE cloud AI)"
    GROQ_OK=true
else
    warn "No Groq API key set (optional free cloud AI — no local GPU needed)"
    echo "     Get a free key at: https://console.groq.com"
    echo "     Then add to config/.env: GROQ_API_KEY=gsk_..."
fi

if [ "$OLLAMA_OK" = false ] && [ "$GROQ_OK" = false ]; then
    echo ""
    warn "No AI provider yet — cover letter generation needs one."
    echo "     Easiest option: sign up free at https://console.groq.com"
    echo "     takes 2 minutes, completely free"
fi

# ── Job source check ─────────────────────────────────────────
hr
echo ""
echo -e "${CYAN}Checking job sources…${NC}"
echo ""

ok "Arbeitnow  — ready (no key needed, EU+UK)"
ok "Remotive   — ready (no key needed, remote roles)"

if [ -n "$ADZUNA_APP_ID" ] && [ -n "$ADZUNA_APP_KEY" ]; then
    ok "Adzuna     — ready (API key found, UK+EU comprehensive)"
else
    warn "Adzuna     — not configured (free key at developer.adzuna.com)"
fi

if [ -n "$REED_API_KEY" ]; then
    ok "Reed       — ready (API key found, UK jobs)"
else
    warn "Reed       — not configured (free key at reed.co.uk/developers)"
fi

# ── Notifications check ──────────────────────────────────────
echo ""
if [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$TELEGRAM_CHAT_ID" ]; then
    ok "Telegram   — configured (you'll get phone notifications)"
else
    warn "Telegram   — not configured (optional but very useful for alerts)"
    echo "     See config/.env.example for setup instructions"
fi

# ── Final summary ────────────────────────────────────────────
hr
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   Setup Complete! 🎉                          ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${CYAN}To start the platform:${NC}"
echo ""
echo -e "    ${GREEN}bash start.sh${NC}"
echo ""
echo -e "  This will:"
echo "    1. Start the backend API on http://localhost:8000"
echo "    2. Open the dashboard in your browser"
echo ""
echo -e "  ${CYAN}First things to do in the dashboard:${NC}"
echo "    1. Go to 'My CVs' and upload your CV"
echo "    2. Go to 'Scraper' and click 'Dry Run' to preview jobs"
echo "    3. Click 'Live Run' to save jobs to your database"
echo "    4. Go to 'Job Matches' and click 'Apply' on any role"
echo "    5. Review the AI-generated cover letter and approve"
echo ""
echo -e "  ${YELLOW}Want more job sources? Add free API keys to config/.env:${NC}"
echo "    Adzuna: https://developer.adzuna.com/"
echo "    Reed:   https://www.reed.co.uk/developers/jobseeker"
echo ""
