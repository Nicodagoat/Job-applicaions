# Job Application Automation Platform

An automated job application platform built for **Niccolò Andrea Nolli**, targeting ESG, sustainability, and climate policy roles in the **United Kingdom and European Economic Area** (Italy excluded).

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Web Dashboard (Browser)                  │
│                  job-automation/frontend/                    │
└───────────────────────────┬─────────────────────────────────┘
                            │ REST API (FastAPI)
┌───────────────────────────▼─────────────────────────────────┐
│                    Backend API Server                        │
│                   backend/main.py :8000                     │
│   /api/jobs  /api/documents  /api/scraper                   │
└──────┬──────────────┬──────────────────┬────────────────────┘
       │              │                  │
┌──────▼──────┐ ┌─────▼──────┐  ┌───────▼──────────┐
│  Scrapers   │ │ AI Module  │  │   Database (DB)  │
│  linkedin   │ │ cover_letter│ │   SQLite / PG    │
│  indeed     │ │ job_analyzer│ │   schema.sql     │
│  (extendable│ │ matching_eng│ │                  │
└──────┬──────┘ └─────┬──────┘  └───────┬──────────┘
       │              │                  │
┌──────▼──────────────▼──────────────────▼──────────┐
│               Orchestrator                         │
│          automation/orchestrator.py                │
└──────────────────────┬────────────────────────────┘
                       │
┌──────────────────────▼────────────────────────────┐
│             Notification System                    │
│         Telegram Bot / Email fallback              │
└────────────────────────────────────────────────────┘
```

---

## Folder Structure

```
job-automation/
├── backend/
│   ├── api/
│   │   ├── jobs.py          # Job & application endpoints
│   │   ├── documents.py     # Document upload endpoints
│   │   └── scraper.py       # Scraper control endpoints
│   ├── models/
│   │   └── job.py           # Pydantic data models
│   ├── services/
│   │   ├── job_service.py   # Job CRUD
│   │   └── document_service.py
│   └── main.py              # FastAPI app entry point
│
├── frontend/
│   └── index.html           # Single-page dashboard
│
├── scrapers/
│   ├── base_scraper.py      # Abstract base with rate limiting
│   ├── linkedin_scraper.py  # LinkedIn public search
│   ├── indeed_scraper.py    # Indeed UK/EU
│   └── scraper_manager.py   # Orchestrates all scrapers
│
├── ai/
│   ├── profile_loader.py    # SINGLE SOURCE OF TRUTH for profile
│   ├── prompts.py           # All AI prompt templates
│   ├── cover_letter_generator.py  # Anti-hallucination AI writer
│   ├── job_analyzer.py      # Extracts requirements from JDs
│   └── matching_engine.py   # Rule-based job scoring
│
├── automation/
│   ├── form_filler.py       # Playwright form automation
│   └── orchestrator.py      # Full pipeline coordinator
│
├── database/
│   ├── schema.sql           # Full database schema
│   └── db.py                # Connection management
│
├── notifications/
│   └── notifier.py          # Telegram + email notifier
│
├── documents/               # User document storage (gitignored)
│   ├── resumes/
│   ├── cover_letters/
│   ├── certificates/
│   └── other/
│
├── config/
│   ├── profile.yaml         # Job preferences & targeting
│   ├── settings.yaml        # System configuration
│   └── .env.example         # Environment variable template
│
├── logs/                    # Application logs (gitignored)
├── tests/
│   └── test_matching_engine.py
│
├── requirements.txt
├── run.py                   # CLI entry point
└── .gitignore
```

---

## Quick Start

### 1. Clone and navigate

```bash
git clone https://github.com/Nicodagoat/Job-applicaions.git
cd Job-applicaions/job-automation
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Playwright browsers (for form automation)

```bash
playwright install chromium
```

### 5. Configure environment variables

```bash
cp config/.env.example config/.env
# Edit config/.env and fill in your API keys
```

Minimum required keys:
| Key | Required for |
|-----|-------------|
| `OPENAI_API_KEY` | Cover letter generation, job analysis |
| `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` | Phone notifications |

### 6. Initialise the database

```bash
python run.py init-db
```

### 7. Upload your CV

Open `http://localhost:8000/docs` after starting the API and use the document upload endpoint,
or open the dashboard and go to **Documents → Upload**.

### 8. Start the backend API

```bash
python run.py api
```

### 9. Open the dashboard

```bash
cd frontend && python3 -m http.server 3000
# Visit: http://localhost:3000
```

---

## Usage

### Run the scraper (dry run first)

```bash
python run.py scrape          # Dry run — logs what would be found
python run.py scrape --live   # Actually saves jobs to database
```

### Run the full pipeline

```bash
python run.py pipeline
```

This will:
1. Scrape LinkedIn and Indeed
2. Score all jobs against your profile
3. Generate AI cover letters for high-match roles
4. Create pending applications
5. Notify you via Telegram

### Test notifications

```bash
python run.py notify-test
```

### Run tests

```bash
pytest tests/
```

---

## Configuration

### Job targeting — `config/profile.yaml`

Key settings to personalise:

```yaml
job_titles:
  primary:
    - "Sustainability Specialist"
    - "ESG Consultant"

application:
  min_match_score: 65       # Don't process jobs below this score
  require_approval: true    # Always request human approval

locations:
  excluded_countries:
    - "Italy"               # Never apply to Italian roles
```

### Safety settings — `config/settings.yaml`

```yaml
safety:
  dry_run: true              # Set to false to actually submit
  human_approval_required: true
  max_daily_applications: 10
```

**`dry_run: true` is the default.** The system will never submit without
you explicitly setting this to `false` and approving each application in the dashboard.

---

## AI Anti-Hallucination Rules

The AI is strictly constrained to use **only** data from `ai/profile_loader.py`:

- `PROFILE_FACTS` is the canonical hardcoded source of truth (from your real CV)
- The system prompt explicitly forbids inventing skills, experience, or qualifications
- A post-generation check flags suspicious patterns
- Any flagged cover letter is marked `requires_review: true` and you receive a notification
- If information is missing, the system **pauses and notifies you** rather than guessing

---

## Notifications Setup (Telegram)

1. Message `@BotFather` on Telegram → `/newbot` → follow prompts
2. Copy the **Bot Token** to `TELEGRAM_BOT_TOKEN` in `config/.env`
3. Message your bot, then visit:
   `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
4. Copy your `chat.id` to `TELEGRAM_CHAT_ID`
5. Test: `python run.py notify-test`

---

## Security Recommendations

1. **Never commit `config/.env`** — it is gitignored
2. **Rate limiting** is built-in — do not lower delays (risk of IP bans)
3. **Human approval is on by default** — review every application before submission
4. All actions are logged in `logs/app.log` and the `audit_log` database table
5. Documents are stored locally and not sent to any external service
6. For cloud deployment: use a secrets manager instead of `.env`

---

## Extending the Platform

### Add a new job board scraper

1. Create `scrapers/my_scraper.py` extending `BaseScraper`
2. Implement `scrape()` returning the standard job dict
3. Add it to `ScraperManager.__init__()` in `scrapers/scraper_manager.py`

### Switch to PostgreSQL

Set `database.type: postgresql` in `config/settings.yaml` and provide
`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` in `.env`.

---

## License

Private — for personal use only.