"""
Jobs API endpoints.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Body

from backend.models.job import ApplicationCreate, ApplicationUpdate
from backend.services.job_service import (
    create_application,
    get_job,
    list_jobs,
    list_applications,
    approve_application,
    update_application_status,
    delete_job,
)
from ai.cover_letter_generator import CoverLetterGenerator
from ai.matching_engine import MatchingEngine
from database.db import get_db, row_to_dict

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])


# --------------------------------------------------------------------------- #
# Job Listings                                                                 #
# --------------------------------------------------------------------------- #

@router.get("/")
def get_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    min_score: float = Query(0, ge=0, le=100),
    search: Optional[str] = Query(None),
):
    return list_jobs(page=page, page_size=page_size, min_score=min_score, search=search)


@router.get("/{job_id}")
def get_job_detail(job_id: int):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.delete("/{job_id}")
def remove_job(job_id: int):
    if not delete_job(job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    return {"message": "Job deleted"}


# --------------------------------------------------------------------------- #
# Applications                                                                 #
# --------------------------------------------------------------------------- #

@router.get("/applications/")
def get_applications(
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    return list_applications(status=status, page=page, page_size=page_size)


@router.post("/{job_id}/apply")
def create_application_endpoint(job_id: int, data: ApplicationCreate):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    application = create_application(job_id=job_id, notes=data.notes)
    return application


@router.post("/applications/{app_id}/approve")
def approve_application_endpoint(app_id: int):
    app = approve_application(app_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    return app


@router.patch("/applications/{app_id}")
def update_application(app_id: int, data: ApplicationUpdate):
    if data.application_status:
        app = update_application_status(
            app_id, data.application_status, data.notes
        )
    else:
        with get_db() as conn:
            conn.execute(
                "UPDATE applications SET notes = COALESCE(?, notes), updated_at = datetime('now') WHERE id = ?",
                (data.notes, app_id)
            )
            conn.commit()
            row = conn.execute("SELECT * FROM applications WHERE id = ?", (app_id,)).fetchone()
            app = row_to_dict(row) if row else None
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    return app


# --------------------------------------------------------------------------- #
# Cover Letter Generation                                                      #
# --------------------------------------------------------------------------- #

@router.post("/{job_id}/cover-letter")
def generate_cover_letter(
    job_id: int,
    tone: str = Body("professional", embed=True),
    max_words: int = Body(350, embed=True),
):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    try:
        generator = CoverLetterGenerator()
        import json
        requirements = json.loads(job.get("requirements") or "[]")
        result = generator.generate(
            job_title=job["job_title"],
            company=job["company"],
            job_description=job.get("description", ""),
            requirements=requirements,
            tone=tone,
            max_words=max_words,
        )
        # Save to database
        with get_db() as conn:
            import json as _json
            conn.execute(
                """
                INSERT INTO cover_letters (job_id, content, ai_model, sources_used)
                VALUES (?, ?, ?, ?)
                """,
                (
                    job_id,
                    result["content"],
                    "gpt-4o-mini",
                    _json.dumps(result["sources_used"]),
                ),
            )
            conn.commit()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --------------------------------------------------------------------------- #
# Stats                                                                        #
# --------------------------------------------------------------------------- #

@router.get("/stats/summary")
def get_stats():
    with get_db() as conn:
        total_jobs = conn.execute("SELECT COUNT(*) FROM job_listings").fetchone()[0]
        high_match = conn.execute(
            "SELECT COUNT(*) FROM job_listings WHERE match_score >= 70"
        ).fetchone()[0]
        apps = conn.execute(
            "SELECT application_status, COUNT(*) as cnt FROM applications GROUP BY application_status"
        ).fetchall()
        tasks_pending = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE status = 'pending'"
        ).fetchone()[0]

    app_stats = {row["application_status"]: row["cnt"] for row in apps}

    return {
        "total_jobs_found": total_jobs,
        "high_match_jobs": high_match,
        "applications": app_stats,
        "pending_tasks": tasks_pending,
    }
