"""
Scraper control API endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from typing import Optional

from database.db import get_db, rows_to_list

router = APIRouter(prefix="/api/scraper", tags=["Scraper"])


def _run_scraper_task(dry_run: bool, sources: Optional[list[str]]) -> None:
    """Background task — runs the scraper and saves results."""
    try:
        from scrapers.scraper_manager import ScraperManager
        manager = ScraperManager()
        manager.run(dry_run=dry_run, sources=sources)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Scraper task failed: {e}")


@router.post("/run")
def trigger_scraper(
    background_tasks: BackgroundTasks,
    dry_run: bool = Query(True),
    sources: Optional[str] = Query(None, description="Comma-separated: linkedin,indeed"),
):
    """
    Trigger a scraping run. Runs in the background.
    Set dry_run=false to actually save results.
    """
    source_list = sources.split(",") if sources else None
    background_tasks.add_task(_run_scraper_task, dry_run, source_list)
    return {
        "message": "Scraper started in background",
        "dry_run": dry_run,
        "sources": source_list or "all",
    }


@router.get("/runs")
def get_scraping_runs(limit: int = Query(10, ge=1, le=100)):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM scraping_runs ORDER BY started_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return rows_to_list(rows)


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
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Task not found")
        conn.execute(
            "UPDATE tasks SET status = 'completed', completed_at = datetime('now') WHERE id = ?",
            (task_id,)
        )
        conn.commit()
    return {"message": "Task completed"}
