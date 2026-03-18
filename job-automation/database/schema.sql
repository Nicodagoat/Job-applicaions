-- ============================================================
-- JOB APPLICATION PLATFORM — DATABASE SCHEMA v2
-- Added: is_active, verified_at, closed_reason, source_type
-- ============================================================

-- Job Listings -----------------------------------------------
CREATE TABLE IF NOT EXISTS job_listings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id     TEXT,
    job_title       TEXT NOT NULL,
    company         TEXT NOT NULL,
    location        TEXT,
    country         TEXT,
    remote          BOOLEAN DEFAULT FALSE,
    source          TEXT NOT NULL,
    source_url      TEXT,
    description     TEXT,
    requirements    TEXT,
    salary_min      INTEGER,
    salary_max      INTEGER,
    salary_currency TEXT DEFAULT 'GBP',
    posted_date     TEXT,
    deadline        TEXT,
    match_score     REAL DEFAULT 0,
    match_breakdown TEXT,
    priority        TEXT DEFAULT 'normal',
    esg_relevant    BOOLEAN DEFAULT FALSE,
    -- Validation fields (v2)
    is_active       BOOLEAN DEFAULT TRUE,   -- FALSE = job is closed/expired
    verified_at     TEXT,                   -- Last time we confirmed it was open
    closed_reason   TEXT,                   -- Why we think it's closed
    discovered_at   TEXT DEFAULT (datetime('now')),
    last_updated    TEXT DEFAULT (datetime('now')),
    raw_data        TEXT,
    UNIQUE(source, external_id)
);

-- Applications -----------------------------------------------
CREATE TABLE IF NOT EXISTS applications (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id               INTEGER NOT NULL REFERENCES job_listings(id),
    application_status   TEXT DEFAULT 'pending',
    date_applied         TEXT,
    cover_letter_id      INTEGER REFERENCES documents(id),
    resume_id            INTEGER REFERENCES documents(id),
    submission_method    TEXT,
    form_url             TEXT,
    confirmation_code    TEXT,
    notes                TEXT,
    next_action_required TEXT,
    next_action_due      TEXT,
    human_approved       BOOLEAN DEFAULT FALSE,
    approved_at          TEXT,
    approved_by          TEXT DEFAULT 'user',
    submitted_at         TEXT,
    automation_log       TEXT,
    created_at           TEXT DEFAULT (datetime('now')),
    updated_at           TEXT DEFAULT (datetime('now'))
);

-- Documents --------------------------------------------------
CREATE TABLE IF NOT EXISTS documents (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_type      TEXT NOT NULL,
    file_name     TEXT NOT NULL,
    file_path     TEXT NOT NULL,
    version       TEXT,
    description   TEXT,
    is_default    BOOLEAN DEFAULT FALSE,
    created_for   INTEGER REFERENCES job_listings(id),
    created_at    TEXT DEFAULT (datetime('now')),
    file_size     INTEGER,
    mime_type     TEXT
);

-- Cover Letters ----------------------------------------------
CREATE TABLE IF NOT EXISTS cover_letters (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id        INTEGER REFERENCES job_listings(id),
    content       TEXT NOT NULL,
    ai_model      TEXT,
    prompt_used   TEXT,
    sources_used  TEXT,
    human_edited  BOOLEAN DEFAULT FALSE,
    approved      BOOLEAN DEFAULT FALSE,
    created_at    TEXT DEFAULT (datetime('now')),
    updated_at    TEXT DEFAULT (datetime('now'))
);

-- Tasks ------------------------------------------------------
CREATE TABLE IF NOT EXISTS tasks (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type         TEXT NOT NULL,
    job_id            INTEGER REFERENCES job_listings(id),
    application_id    INTEGER REFERENCES applications(id),
    title             TEXT NOT NULL,
    description       TEXT,
    status            TEXT DEFAULT 'pending',
    priority          TEXT DEFAULT 'normal',
    due_at            TEXT,
    completed_at      TEXT,
    notification_sent BOOLEAN DEFAULT FALSE,
    created_at        TEXT DEFAULT (datetime('now'))
);

-- Scraping Runs ----------------------------------------------
CREATE TABLE IF NOT EXISTS scraping_runs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    source       TEXT NOT NULL,
    started_at   TEXT DEFAULT (datetime('now')),
    finished_at  TEXT,
    status       TEXT DEFAULT 'running',
    jobs_found   INTEGER DEFAULT 0,
    jobs_new     INTEGER DEFAULT 0,
    error        TEXT,
    metadata     TEXT
);

-- Audit Log --------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    entity     TEXT,
    entity_id  INTEGER,
    action     TEXT NOT NULL,
    details    TEXT,
    ip_address TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Indexes ----------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_jobs_score     ON job_listings(match_score, is_active);
CREATE INDEX IF NOT EXISTS idx_jobs_active    ON job_listings(is_active, discovered_at);
CREATE INDEX IF NOT EXISTS idx_jobs_company   ON job_listings(company);
CREATE INDEX IF NOT EXISTS idx_apps_status    ON applications(application_status);
CREATE INDEX IF NOT EXISTS idx_apps_job       ON applications(job_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status   ON tasks(status, priority);
