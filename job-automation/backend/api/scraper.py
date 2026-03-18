"""
Scraper control API endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from typing import Optional

from database.db import get_db, rows_to_list

router = APIRouter(prefix="/api/scraper", tags=["Scraper"])


def _run_scraper_task(dry_run: bool, sources: Optional[list[str]], validate: bool) -> None:
    try:
        from scrapers.scraper_manager import ScraperManager
        ScraperManager().run(dry_run=dry_run, sources=sources, validate=validate)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Scraper task failed: {e}")


@router.post("/run")
def trigger_scraper(
    background_tasks: BackgroundTasks,
    dry_run: bool = Query(True),
    validate: bool = Query(True, description="Validate jobs are still open"),
    sources: Optional[str] = Query(None, description="Comma-separated: arbeitnow,remotive,adzuna,reed"),
):
    """
    Trigger a scraping run in the background.
    dry_run=true  → preview only (no database writes)
    dry_run=false → save jobs to database
    validate=true → verify jobs are still open (recommended)
    """
    source_list = [s.strip() for s in sources.split(",")] if sources else None
    background_tasks.add_task(_run_scraper_task, dry_run, source_list, validate)
    return {
        "message": "Scraper started in background. Check /api/scraper/runs for progress.",
        "dry_run":  dry_run,
        "validate": validate,
        "sources":  source_list or "all",
    }


@router.get("/runs")
def get_scraping_runs(limit: int = Query(10, ge=1, le=100)):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM scraping_runs ORDER BY started_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return rows_to_list(rows)


@router.get("/sources")
def get_available_sources():
    """
    Returns which job sources are configured and available.
    """
    import os
    sources = [
        {
            "name":        "arbeitnow",
            "label":       "Arbeitnow",
            "description": "EU + UK jobs — completely free, no key needed",
            "configured":  True,
            "free":        True,
        },
        {
            "name":        "remotive",
            "label":       "Remotive",
            "description": "Remote jobs worldwide — completely free, no key needed",
            "configured":  True,
            "free":        True,
        },
        {
            "name":        "adzuna",
            "label":       "Adzuna",
            "description": "Comprehensive UK + EU — free API key (developer.adzuna.com)",
            "configured":  bool(os.environ.get("ADZUNA_APP_ID") and os.environ.get("ADZUNA_APP_KEY")),
            "free":        True,
            "setup_url":   "https://developer.adzuna.com/",
        },
        {
            "name":        "reed",
            "label":       "Reed.co.uk",
            "description": "UK's largest job board — free API key (reed.co.uk/developers)",
            "configured":  bool(os.environ.get("REED_API_KEY")),
            "free":        True,
            "setup_url":   "https://www.reed.co.uk/developers/jobseeker",
        },
        {
            "name":        "linkedin",
            "label":       "LinkedIn",
            "description": "LinkedIn Jobs — web scraping (may be rate-limited)",
            "configured":  True,
            "free":        True,
        },
    ]
    return sources


@router.post("/validate")
def validate_jobs(
    background_tasks: BackgroundTasks,
    max_jobs: int = Query(50, ge=1, le=200),
):
    """Re-validate stored jobs to check they are still open."""
    def _validate():
        from scrapers.job_validator import JobValidator
        result = JobValidator().revalidate_stale_jobs(max_jobs=max_jobs)
        import logging
        logging.getLogger(__name__).info(f"Validation complete: {result}")

    background_tasks.add_task(_validate)
    return {"message": f"Validating up to {max_jobs} jobs in background"}


@router.get("/validation-stats")
def validation_stats():
    from scrapers.job_validator import JobValidator
    return JobValidator().get_validation_stats()


@router.get("/tasks")
def get_pending_tasks():
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT t.*, j.job_title, j.company, j.source_url
            FROM tasks t
            LEFT JOIN job_listings j ON t.job_id = j.id
            WHERE t.status = 'pending'
            ORDER BY t.priority DESC, t.created_at ASC
            """
        ).fetchall()
    return rows_to_list(rows)


@router.patch("/tasks/{task_id}/complete")
def complete_task(task_id: int):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Task not found")
        conn.execute(
            "UPDATE tasks SET status='completed', completed_at=datetime('now') WHERE id=?",
            (task_id,)
        )
        conn.commit()
    return {"message": "Task completed"}
