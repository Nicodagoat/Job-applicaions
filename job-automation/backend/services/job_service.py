"""
Job listings CRUD service.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from database.db import get_db, rows_to_list, row_to_dict
from backend.models.job import JobListingCreate


# --------------------------------------------------------------------------- #
# Job Listings                                                                 #
# --------------------------------------------------------------------------- #

def create_job(job: JobListingCreate) -> dict:
    """Insert a new job listing. Returns the created record."""
    with get_db() as conn:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO job_listings
                (external_id, job_title, company, location, country, remote,
                 source, source_url, description, requirements,
                 salary_min, salary_max, salary_currency,
                 posted_date, deadline, esg_relevant, raw_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job.external_id,
                job.job_title,
                job.company,
                job.location,
                job.country,
                job.remote,
                job.source,
                job.source_url,
                job.description,
                json.dumps(job.requirements) if job.requirements else None,
                job.salary_min,
                job.salary_max,
                job.salary_currency,
                job.posted_date,
                job.deadline,
                job.esg_relevant,
                json.dumps(job.raw_data) if job.raw_data else None,
            ),
        )
        conn.commit()
        job_id = cursor.lastrowid
        return get_job(job_id) if job_id else {}


def get_job(job_id: int) -> Optional[dict]:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM job_listings WHERE id = ?", (job_id,)
        ).fetchone()
        return row_to_dict(row) if row else None


def list_jobs(
    page: int = 1,
    page_size: int = 20,
    min_score: float = 0,
    status_filter: Optional[str] = None,
    search: Optional[str] = None,
) -> dict:
    offset = (page - 1) * page_size
    conditions = ["match_score >= ?"]
    params: list = [min_score]

    if search:
        conditions.append("(job_title LIKE ? OR company LIKE ? OR description LIKE ?)")
        term = f"%{search}%"
        params.extend([term, term, term])

    where = " AND ".join(conditions)

    with get_db() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM job_listings WHERE {where}", params
        ).fetchone()[0]

        rows = conn.execute(
            f"""
            SELECT * FROM job_listings
            WHERE {where}
            ORDER BY match_score DESC, discovered_at DESC
            LIMIT ? OFFSET ?
            """,
            params + [page_size, offset],
        ).fetchall()

    return {
        "items": rows_to_list(rows),
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_next": (offset + page_size) < total,
    }


def update_job_score(job_id: int, score: float, breakdown: dict) -> None:
    priority = "normal"
    if score >= 85:
        priority = "priority"
    elif score >= 70:
        priority = "high"
    elif score < 50:
        priority = "low"

    with get_db() as conn:
        conn.execute(
            """
            UPDATE job_listings
            SET match_score = ?, match_breakdown = ?, priority = ?,
                last_updated = datetime('now')
            WHERE id = ?
            """,
            (score, json.dumps(breakdown), priority, job_id),
        )
        conn.commit()


def delete_job(job_id: int) -> bool:
    with get_db() as conn:
        cursor = conn.execute("DELETE FROM job_listings WHERE id = ?", (job_id,))
        conn.commit()
        return cursor.rowcount > 0


# --------------------------------------------------------------------------- #
# Applications                                                                 #
# --------------------------------------------------------------------------- #

def create_application(job_id: int, notes: Optional[str] = None) -> dict:
    with get_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO applications (job_id, notes)
            VALUES (?, ?)
            """,
            (job_id, notes),
        )
        conn.commit()
        return get_application(cursor.lastrowid)


def get_application(app_id: int) -> Optional[dict]:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM applications WHERE id = ?", (app_id,)
        ).fetchone()
        return row_to_dict(row) if row else None


def list_applications(
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    offset = (page - 1) * page_size
    conditions = []
    params: list = []

    if status:
        conditions.append("application_status = ?")
        params.append(status)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    with get_db() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM applications {where}", params
        ).fetchone()[0]

        rows = conn.execute(
            f"""
            SELECT a.*, j.job_title, j.company, j.location, j.source_url
            FROM applications a
            JOIN job_listings j ON a.job_id = j.id
            {where}
            ORDER BY a.created_at DESC
            LIMIT ? OFFSET ?
            """,
            params + [page_size, offset],
        ).fetchall()

    return {
        "items": rows_to_list(rows),
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_next": (offset + page_size) < total,
    }


def approve_application(app_id: int) -> Optional[dict]:
    with get_db() as conn:
        conn.execute(
            """
            UPDATE applications
            SET human_approved = 1, approved_at = datetime('now'),
                application_status = 'approved', updated_at = datetime('now')
            WHERE id = ?
            """,
            (app_id,),
        )
        conn.commit()
        return get_application(app_id)


def update_application_status(app_id: int, status: str, notes: Optional[str] = None) -> Optional[dict]:
    with get_db() as conn:
        conn.execute(
            """
            UPDATE applications
            SET application_status = ?, notes = COALESCE(?, notes),
                updated_at = datetime('now')
            WHERE id = ?
            """,
            (status, notes, app_id),
        )
        conn.commit()
        return get_application(app_id)
